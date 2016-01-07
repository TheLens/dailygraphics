
import boto
import json
import os
import csv
import xlrd
from slugify import slugify
import subprocess
import webbrowser

from distutils.spawn import find_executable
from fabric.api import local, require, task
from fabric.state import env
from oauth import get_document, get_credentials
from time import sleep

import app_config
import assets
import flat
import render
import utils

from render_utils import load_graphic_config

SPREADSHEET_COPY_URL_TEMPLATE = 'https://www.googleapis.com/drive/v2/files/' + \
    '%s/copy'
SPREADSHEET_VIEW_TEMPLATE = 'https://docs.google.com/spreadsheet/ccc?key=' + \
    '%s#gid=1'

"""
Base configuration
"""
env.settings = None

"""
Environments

Changing environment requires a full-stack test.
An environment points to both a server and an S3
bucket.
"""


@task
def production():
    """
    Run as though on production.
    """
    env.settings = 'production'
    app_config.configure_targets(env.settings)


@task
def staging():
    """
    Run as though on staging.
    """
    env.settings = 'staging'
    app_config.configure_targets(env.settings)

"""
Running the app
"""


@task
def app(port='8000'):
    """
    Serve app.py.
    """
    local(
        'gunicorn -b 0.0.0.0:%s ' % port +
        '--timeout 3600 --reload app:wsgi_app')  # --debug

"""
Deployment

Changes to deployment requires a full-stack test. Deployment
has two primary functions: Pushing flat files to S3 and deploying
code to a remote server if required.
"""


@task
def deploy(*slugs):
    """
    Deploy the latest app(s) to S3 and, if configured, to our servers.
    """
    if slugs[0] == '':
        print 'You must specify at least one slug, like this: "deploy:slug"' + \
            ' or "deploy:slug,slug"'
        return

    for slug in slugs:
        deploy_single(slug)


def deploy_single(slug):
    """
    Deploy a single project to S3 and, if configured, to our servers.
    """
    require('settings', provided_by=[production, staging])

    graphic_root = '%s/%s' % (app_config.GRAPHICS_PATH, slug)
    s3_root = '%s/graphics/%s' % (app_config.PROJECT_SLUG, slug)
    graphic_assets = '%s/assets' % graphic_root
    s3_assets = '%s/assets' % s3_root

    # New to The Lens. Check if fallback image has been created
    if not os.path.isfile('%s/fallback.png' % graphic_root):
        print 'Render a fallback image before deploying. ' + \
            'Run "fab render.save_fallback_image:slug".'
        return

    graphic_config = load_graphic_config(graphic_root)

    use_assets = getattr(graphic_config, 'USE_ASSETS', True)
    default_max_age = getattr(
        graphic_config, 'DEFAULT_MAX_AGE', None) or app_config.DEFAULT_MAX_AGE
    assets_max_age = getattr(
        graphic_config, 'ASSETS_MAX_AGE', None) or app_config.ASSETS_MAX_AGE

    update_copy(slug)

    if use_assets:
        assets.sync(slug)

    render.render(slug)

    flat.deploy_folder(
        graphic_root,
        s3_root,
        headers={
            'Cache-Control': 'max-age=%i' % default_max_age
        },
        ignore=['%s/*' % graphic_assets]
    )

    # Deploy parent assets
    flat.deploy_folder(
        'www',
        app_config.PROJECT_SLUG,
        headers={
            'Cache-Control': 'max-age=%i' % default_max_age
        }
    )

    if use_assets:
        flat.deploy_folder(
            graphic_assets,
            s3_assets,
            headers={
                'Cache-Control': 'max-age=%i' % assets_max_age
            }
        )

    print '\n%s URL: %s/graphics/%s/' % (
        env.settings.capitalize(), app_config.S3_BASE_URL, slug)


@task
def deploy_templates():
    '''
    Syncs local templates directory with staging and production.

    New for The Lens.
    '''

    temp_dir = '/Users/thomasthoren/projects/dailygraphics/graphic_templates'

    s3_staging_url = 's3://staging-projects.thelensnola.org/' + \
        'dailygraphics/templates'
    s3_production_url = 's3://projects.thelensnola.org/dailygraphics/templates'

    # Sync everything to S3.
    local(
        'aws s3 sync ' +
        '%s/ ' % temp_dir +
        's3://staging-projects.thelensnola.org/dailygraphics/templates/ ' +
        '--exclude "_base/*" ' +
        '--exclude "_thumbs/*" ' +
        '--exclude "*.DS_Store" ' +
        '--acl public-read')
    local(
        'aws s3 sync ' +
        '%s/ ' % temp_dir +
        's3://projects.thelensnola.org/dailygraphics/templates/ ' +
        '--exclude "_base/*" ' +
        '--exclude "_thumbs/*" ' +
        '--exclude "*.DS_Store" ' +
        '--acl public-read')

    # Copy pym.js to directories.
    awscli_string = 'aws s3 sync %s/_base/js/ %s/%s/js/ --acl public-read'

    local(awscli_string % (temp_dir, s3_staging_url, 'bar_chart'))
    local(awscli_string % (temp_dir, s3_staging_url, 'block_histogram'))
    local(awscli_string % (temp_dir, s3_staging_url, 'column_chart'))
    local(awscli_string % (temp_dir, s3_staging_url, 'dot_chart'))
    local(awscli_string % (temp_dir, s3_staging_url, 'grouped_bar_chart'))
    local(awscli_string % (temp_dir, s3_staging_url, 'line_chart'))
    local(awscli_string % (temp_dir, s3_staging_url, 'locator_map'))
    local(awscli_string % (temp_dir, s3_staging_url, 'slopegraph'))
    local(awscli_string % (temp_dir, s3_staging_url, 'stacked_bar_chart'))
    local(awscli_string % (temp_dir, s3_staging_url, 'stacked_column_chart'))
    local(awscli_string % (temp_dir, s3_staging_url, 'state_grid_map'))
    local(awscli_string % (temp_dir, s3_staging_url, 'table'))

    local(awscli_string % (temp_dir, s3_production_url, 'bar_chart'))
    local(awscli_string % (temp_dir, s3_production_url, 'block_histogram'))
    local(awscli_string % (temp_dir, s3_production_url, 'column_chart'))
    local(awscli_string % (temp_dir, s3_production_url, 'dot_chart'))
    local(awscli_string % (temp_dir, s3_production_url, 'grouped_bar_chart'))
    local(awscli_string % (temp_dir, s3_production_url, 'line_chart'))
    local(awscli_string % (temp_dir, s3_production_url, 'locator_map'))
    local(awscli_string % (temp_dir, s3_production_url, 'slopegraph'))
    local(awscli_string % (temp_dir, s3_production_url, 'stacked_bar_chart'))
    local(awscli_string % (temp_dir, s3_production_url, 'stacked_column_chart'))
    local(awscli_string % (temp_dir, s3_production_url, 'state_grid_map'))
    local(awscli_string % (temp_dir, s3_production_url, 'table'))


@task
def deploy_table_of_contents():
    '''
    Syncs table of contents with S3.

    New for The Lens.
    '''

    local(
        'aws s3 cp ' +
        '/Users/thomasthoren/projects/dailygraphics/index.html ' +
        's3://staging-projects.thelensnola.org/dailygraphics/index.html ' +
        '--acl public-read')

    local(
        'aws s3 cp ' +
        '/Users/thomasthoren/projects/dailygraphics/index.html ' +
        's3://projects.thelensnola.org/dailygraphics/index.html ' +
        '--acl public-read')


def download_copy(slug):
    """
    Downloads a Google Doc as an .xlsx file.
    """
    graphic_path = '%s/%s' % (app_config.GRAPHICS_PATH, slug)

    try:
        graphic_config = load_graphic_config(graphic_path)
    except IOError:
        print '%s/graphic_config.py does not exist.' % slug
        return

    # The new file's Google key ID.
    new_file_key = graphic_config.COPY_GOOGLE_DOC_KEY

    if not hasattr(graphic_config, 'COPY_GOOGLE_DOC_KEY') or not new_file_key:
        print 'COPY_GOOGLE_DOC_KEY is not defined in ' + \
            '%s/graphic_config.py.' % slug
        return

    copy_path = os.path.join(graphic_path, '%s.xlsx' % slug)
    get_document(new_file_key, copy_path)


@task
def save_sheet_as_csv(slug):
    '''
    Extracts a sheet as CSV from the Google Sheet download (Excel workbook).

    Only allows for one tab for now.
    '''

    graphic_path = '%s/%s' % (app_config.GRAPHICS_PATH, slug)
    workbook_file = os.path.join(graphic_path, '%s.xlsx' % slug)

    sheet_id = 3  # The targeted tab (zero-based index).

    workbook = xlrd.open_workbook(workbook_file)
    # datemode = workbook.datemode
    worksheets = workbook.sheet_names()
    worksheet = workbook.sheet_by_name(worksheets[sheet_id])

    headers = {}
    cell_id = 0
    row_id = 0
    while cell_id < worksheet.ncols:
        cell_type = worksheet.cell_type(row_id, cell_id)
        cell_value = worksheet.cell_value(row_id, cell_id)
        cell_value = str(slugify(cell_value).replace('-', '_')).strip()
        if cell_type == 1:  # If unicode
            headers[cell_id] = cell_value
        cell_id += 1

    csv_file = os.path.join(graphic_path, 'data/external.csv')

    with open(csv_file, "w") as filename:
        writer = csv.DictWriter(filename, fieldnames=headers.values())
        writer.writeheader()

        row_id = 1
        while row_id < worksheet.nrows:
            cell_id = 0
            row_dict = {}
            while cell_id < worksheet.ncols:
                header = headers[cell_id]

                cell_value = worksheet.cell_value(row_id, cell_id)

                row_dict[header] = cell_value
                cell_id += 1

            writer.writerow(row_dict)
            row_id += 1


@task
def update_copy(slug=None):
    """
    Fetches the latest Google Doc and updates local JSON.
    """
    if slug:
        download_copy(slug)
        # save_sheet_as_csv(slug)  # Only want to run after mapturner
        return

    slugs = os.listdir(app_config.GRAPHICS_PATH)

    for slug in slugs:
        graphic_path = '%s/%s' % (app_config.GRAPHICS_PATH, slug)

        if not os.path.exists('%s/graphic_config.py' % graphic_path):
            continue

        print slug
        download_copy(slug)
        # save_sheet_as_csv(slug)  # Only want to run after mapturner


"""
App-specific commands
"""


def _add_graphic(slug, template):
    """
    Create a graphic with `slug` from `template`
    """
    graphic_path = '%s/%s' % (app_config.GRAPHICS_PATH, slug)

    if _check_slug(slug):
        return

    local('cp -r graphic_templates/_base %s' % (graphic_path))
    local('cp -r graphic_templates/%s/* %s' % (template, graphic_path))

    config_path = os.path.join(graphic_path, 'graphic_config.py')

    if os.path.isfile(config_path):
        print 'Creating spreadsheet...'

        success = copy_spreadsheet(slug)

        if success:
            download_copy(slug)
            # save_sheet_as_csv(slug)  # Only want to run after mapturner
        else:
            local('rm -r graphic_path')
            print 'Failed to copy spreadsheet! Try again!'
            return
    else:
        print 'No graphic_config.py found, not creating spreadsheet'

    print 'Run `fab app` and visit http://127.0.0.1:8000/graphics/' + \
        '%s to view' % slug

    # local('open http://127.0.0.1:8000/graphics/%s' % slug)


def _check_slug(slug):
    """
    Does slug exist in graphics folder or production s3 bucket?
    """
    graphic_path = '%s/%s' % (app_config.GRAPHICS_PATH, slug)
    if os.path.isdir(graphic_path):
        print 'Error: Directory already exists'
        return True

    try:
        bucket = utils.get_bucket(
            app_config.PRODUCTION_S3_BUCKET['bucket_name'])
        key = bucket.get_key('%s/graphics/%s/child.html' % (
            app_config.PROJECT_SLUG, slug))

        if key:
            print 'Error: Slug already exists either locally or on S3.'
            return True
    except boto.exception.NoAuthHandlerFound:
        print 'Could not authenticate, skipping Amazon S3 check'
    except boto.exception.S3ResponseError:
        print 'Could not access S3 bucket, skipping Amazon S3 check'

    return False


@task
def add_graphic(slug):
    """
    Create a basic project.
    """
    _add_graphic(slug, 'graphic')


@task
def add_animated_photo(slug):
    """
    Create a new animated photo (GIF alternative).
    """
    _add_graphic(slug, 'animated_photo')


@task
def add_archive_graphic(slug):
    """
    Create a shell to archive an old project.
    """
    _add_graphic(slug, 'archive_graphic')


@task
def add_bar_chart(slug):
    """
    Create a bar chart.
    """
    _add_graphic(slug, 'bar_chart')


@task
def add_column_chart(slug):
    """
    Create a column chart.
    """
    _add_graphic(slug, 'column_chart')


@task
def add_stacked_column_chart(slug):
    """
    Create a stacked column chart.
    """
    _add_graphic(slug, 'stacked_column_chart')


@task
def add_block_histogram(slug):
    """
    Create a block histogram.
    """
    _add_graphic(slug, 'block_histogram')


@task
def add_grouped_bar_chart(slug):
    """
    Create a grouped bar chart.
    """
    _add_graphic(slug, 'grouped_bar_chart')


@task
def add_stacked_bar_chart(slug):
    """
    Create a stacked bar chart.
    """
    _add_graphic(slug, 'stacked_bar_chart')


@task
def add_state_grid_map(slug):
    """
    Create a state grid cartogram
    """
    _add_graphic(slug, 'state_grid_map')


@task
def add_line_chart(slug):
    """
    Create a line chart.
    """
    _add_graphic(slug, 'line_chart')


@task
def add_dot_chart(slug):
    """
    Create a dot chart with error bars
    """
    _add_graphic(slug, 'dot_chart')


@task
def add_slopegraph(slug):
    """
    Create a slopegraph (intended for narrow display)
    """
    _add_graphic(slug, 'slopegraph')


@task
def add_map(slug):
    """
    Create a locator map.
    """
    _add_graphic(slug, 'locator_map')


@task
def add_table(slug):
    """
    Create a data table.
    """
    _add_graphic(slug, 'table')


@task
def add_issue_matrix(slug):
    """
    Create a table comparing positions on an issue.
    """
    _add_graphic(slug, 'issue_matrix')


def _check_credentials():
    """
    Check credentials and spawn server and browser if not
    """
    credentials = get_credentials()

    scope = credentials.config['google']['scope']
    if not credentials or 'https://www.googleapis.com/auth/drive' not in scope:
        try:
            with open(os.devnull, 'w') as fnull:
                print 'Credentials were not found or permissions were not ' + \
                    'correct. Automatically opening a browser to ' + \
                    'authenticate with Google.'
                gunicorn = find_executable('gunicorn')
                process = subprocess.Popen(
                    [
                        gunicorn,
                        '-b',
                        '127.0.0.1:8888',
                        'app:wsgi_app'
                    ],
                    stdout=fnull,
                    stderr=fnull
                )
                webbrowser.open_new('http://127.0.0.1:8888/oauth')
                print 'Waiting...'
                while not credentials:
                    try:
                        credentials = get_credentials()
                        sleep(1)
                    except ValueError:
                        continue
                print 'Successfully authenticated!'
                process.terminate()
        except KeyboardInterrupt:
            print '\nCtrl-c pressed. Later, skater!'
            exit()


def copy_spreadsheet(slug):
    """
    Copy the template Google spreadsheet into the graphics folder on Drive.
    """
    _check_credentials()

    config_path = '%s/%s/' % (app_config.GRAPHICS_PATH, slug)
    graphic_config = load_graphic_config(config_path)

    new_file_key = graphic_config.COPY_GOOGLE_DOC_KEY

    if not hasattr(graphic_config, 'COPY_GOOGLE_DOC_KEY') or not new_file_key:
        print 'Skipping spreadsheet creation. (COPY_GOOGLE_DOC_KEY is not ' + \
            'defined in %s/graphic_config.py.)' % slug
        return

    req_url = SPREADSHEET_COPY_URL_TEMPLATE % graphic_config.COPY_GOOGLE_DOC_KEY
    kwargs = {
        'credentials': get_credentials(),
        'url': req_url,
        'method': 'POST',
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({
            'title': slug
        }),
    }

    resp = app_config.authomatic.access(**kwargs)

    if resp.status == 200:  # Sucessfully created file
        print resp
        spreadsheet_key = resp.data['id']

        # Copy file in Drive from 'templates' to 'graphics' directory.
        graphics_dir_key = '0B95Rq71MRLfHY0gxUURqbS1tWDg'  # TODO: move to cfg
        request_url = 'https://www.googleapis.com/drive/v2/files/' + \
            '%s/parents' % spreadsheet_key
        kwargs = {
            'credentials': get_credentials(),
            'url': request_url,
            'method': 'POST',
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'id': graphics_dir_key
            })
        }
        resp2 = app_config.authomatic.access(**kwargs)

        if resp2.status == 200:  # Successfully copied file to 'graphics' folder
            # Delete old file from 'templates' directory.
            templates_dir_key = '0B95Rq71MRLfHeTlSNmtnWmEwQ28'
            request_url = 'https://www.googleapis.com/drive/v2/files/' + \
                '%s/parents/%s' % (spreadsheet_key, templates_dir_key)
            kwargs = {
                'credentials': get_credentials(),
                'url': request_url,
                'method': 'DELETE',
                'headers': {'Content-Type': 'application/json'}
            }
            resp3 = app_config.authomatic.access(**kwargs)

            if resp3.status == 204:  # Successfully deleted old file
                spreadsheet_url = SPREADSHEET_VIEW_TEMPLATE % spreadsheet_key
                print 'New spreadsheet created successfully!'
                # local('open %s' % spreadsheet_url)
                print 'View it online at %s' % spreadsheet_url
                utils.replace_in_file(
                    '%s/graphic_config.py' % config_path,
                    graphic_config.COPY_GOOGLE_DOC_KEY,
                    spreadsheet_key)

                return True

                utils.replace_in_file(
                    config_path, graphic_config.COPY_GOOGLE_DOC_KEY, '')

    print 'Error creating spreadsheet (status code %s) with message %s' % (
        resp.status, resp.reason)
    return False
