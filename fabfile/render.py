
import os
import time
from glob import glob
from fabric.api import task
from fabric.state import env

# For fallback.png screenshot
from selenium import webdriver, common
from PIL import Image

import app
import app_config


@task(default=True)
def render(slug=''):
    """
    Render HTML templates and compile assets.
    """
    if slug:
        _render_graphics(['%s/%s' % (app_config.GRAPHICS_PATH, slug)])
        # save_fallback_image(slug)  # TODO
    else:
        _render_graphics(glob('%s/*' % app_config.GRAPHICS_PATH))


def _render_graphics(paths):
    """
    Render a set of graphics
    """
    from flask import g

    # Fake out deployment target
    app_config.configure_targets(env.get('settings', None))

    for path in paths:
        slug = path.split('%s/' % app_config.GRAPHICS_PATH)[1].split('/')[0]

        with app.app.test_request_context(path='graphics/%s/' % slug):
            g.compile_includes = True
            g.compiled_includes = {}

            view = app.graphic.__dict__['_graphics_detail']
            content = view(slug).data

        with open('%s/index.html' % path, 'w') as writefile:
            writefile.write(content)

        # Fallback for legacy projects w/o child templates
        if not os.path.exists('%s/child_template.html' % path):
            continue

        with app.app.test_request_context(path='graphics/%s/child.html' % slug):
            g.compile_includes = True
            g.compiled_includes = {}

            view = app.graphic.__dict__['_graphics_child']
            content = view(slug).data

        with open('%s/child.html' % path, 'w') as writefile:
            writefile.write(content)

    # Un-fake-out deployment target
    app_config.configure_targets(app_config.DEPLOYMENT_TARGET)


def _take_screenshot(slug, graphic_type):
    if graphic_type == 'graphics':
        type_path = '%s/%s' % (app_config.GRAPHICS_PATH, slug)
    else:
        type_path = '%s/%s' % (app_config.TEMPLATES_PATH, slug)

    driver = webdriver.PhantomJS(
        executable_path='/usr/local/bin/phantomjs',
        port=0
    )

    driver.maximize_window()  # Take screenshot large, then shrink for retina.

    graphic_url = 'http://localhost:8000/%s/%s/#desktop' % (graphic_type, slug)

    driver.get(graphic_url)

    time.sleep(5)

    element = driver.find_element_by_xpath(
        "//iframe")
    location = element.location
    size = element.size
    driver.save_screenshot('%s/tmp.png' % type_path)

    im = Image.open('%s/tmp.png' % type_path)

    left = location['x']
    top = location['y']
    right = location['x'] + size['width']
    bottom = location['y'] + size['height']

    im = im.crop((left, top, right, bottom))  # defines crop points
    im.save('%s/fallback.png' % type_path)

    os.remove('%s/tmp.png' % type_path)

    try:
        pass
    except common.exceptions.NoSuchElementException:
        print 'No preview image found.'
    finally:
        driver.close()


@task
def save_fallback_image(slug=None, graphic_type='graphics'):
    '''
    New for The Lens.

    Takes a screenshot of the localhost graphic and uses it as the fallback
    image. Assumes a local server is running.

    If you see a transparent background, be sure you've set a background color.
    '''

    if slug:
        print 'Saving screenshot for %s/%s/fallback.png...' % (
            graphic_type, slug)
        _take_screenshot(slug, graphic_type)
        return

    # Else, save all fallbacks
    print 'Saving fallback.png screenshots for all graphics and templates...'
    graphic_slugs = os.listdir(app_config.GRAPHICS_PATH)
    template_slugs = os.listdir(app_config.TEMPLATES_PATH)

    for graphic_slug in graphic_slugs:
        if graphic_slug[0] == '_' or graphic_slug[0] == '.':
            continue

        print 'Saving %s/%s/fallback.png' % ('graphics', graphic_slug)
        _take_screenshot(graphic_slug, 'graphics')

    for template_slug in template_slugs:
        if template_slug[0] == '_' or template_slug[0] == '.':
            continue

        print 'Saving %s/%s/fallback.png' % ('templates', template_slug)
        _take_screenshot(template_slug, 'templates')
