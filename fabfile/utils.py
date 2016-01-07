
import boto
from boto.s3.connection import OrdinaryCallingFormat
from fabric.api import prompt


def confirm(message):
    '''Verify a users intentions.'''
    answer = prompt(message, default="Not at all")

    if answer.lower() not in ('y', 'yes', 'buzz off', 'screw you'):
        exit()


def replace_in_file(filename, find, replace):
    with open(filename, 'r') as f:
        contents = f.read()

    contents = contents.replace(find, replace)

    with open(filename, 'w') as f:
        f.write(contents)


def get_bucket(bucket_name):
    '''Established a connection and gets s3 bucket.'''

    if '.' in bucket_name:
        # s3 = boto.connect_s3(calling_format=OrdinaryCallingFormat())
        s3 = boto.s3.connect_to_region(
            'us-west-2',
            # aws_access_key_id=AWS_ACCESS_KEY_ID,
            # aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            # is_secure=True,  # uncommmnt if you are not using ssl
            calling_format=OrdinaryCallingFormat())
    else:
        # s3 = boto.connect_s3()
        s3 = boto.s3.connect_to_region(
            'us-west-2'
            # aws_access_key_id=AWS_ACCESS_KEY_ID,
            # aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            # is_secure=True,  # uncommmnt if you are not using ssl
        )

    return s3.get_bucket(bucket_name, validate=False)
