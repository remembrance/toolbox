#!/usr/bin/env python

# simple class to provide minio/s3 functionality
# to other scripts like uploading files

import boto3
import os, sys
import xml.dom.minidom as _xml
from urllib.error import URLError, HTTPError
from os.path import basename

class S3Storage:
    def __init__(self):
        self.config = {}

        # defaults - s3v4 for aws v4 signature
        self.config['signature_version'] = os.getenv('S3_SIGNATURE_VERSION', 's3')
        self.config['verify'] = os.getenv('S3_VERIFY', False)

        # minio/s3
        self.config['host'] = os.getenv('S3_HOST')
        self.config['bucket'] = os.getenv('S3_BUCKET')
        self.config['access_key'] = os.getenv('S3_ACCESS_KEY')
        self.config['secret_key'] = os.getenv('S3_SECRET_KEY')
        self.config['session_token'] = os.getenv('S3_SESSION_TOKEN')

        # if LDAP used - try to retrieve keys from sts api
        if not self.config['access_key'] or not self.config['secret_key']:
            _ldap_user = os.getenv('S3_LDAP_USER')
            _ldap_pass = os.getenv('S3_LDAP_PASS')
            if not _ldap_user or not _ldap_pass or not self.config['host']:
                raise OSError(2, "missing required environment variables to proceed")

            self.config['access_key'], self.config['secret_key'], self.config['session_token'] = self.get_sts_creds(
                    self.config['host'], _ldap_user, _ldap_pass)

        for i in self.config.keys():
            if self.config[i] is None:
                raise OSError(2, f'missing required config key or environment variable "{i}" proceed')

    def get_sts_creds(self, sts_url, username, password):
        def get(dom, key):
            try:
                result = dom.getElementsByTagName('AssumeRoleWithLDAPIdentityResult')[0]
                creds = result.getElementsByTagName('Credentials')[0]
                return creds.getElementsByTagName(key)[0].firstChild.nodeValue
            except IndexError as e:
                print(f'error accessing response key {key}')
                sys.exit(1)

        from urllib import request, parse
        payload = {
            'Action': 'AssumeRoleWithLDAPIdentity',
            'LDAPUsername': username,
            'LDAPPassword': password,
            'Version': '2011-06-15',
            'Duration': '3600'
        }
        data = parse.urlencode(payload).encode()
        req =  request.Request(sts_url, data=data, method='POST')
        try:
            with request.urlopen(req) as resp:
                with _xml.parseString(resp.read()) as dom:
                    assert dom.documentElement.tagName == 'AssumeRoleWithLDAPIdentityResponse'
                    return get(dom, 'AccessKeyId'), get(dom, 'SecretAccessKey'), get(dom, 'SessionToken')

        except HTTPError as e:
            print(f'error communicating with {sts_url}: {e.read().decode()}')
            sys.exit(1)
        except URLError as e:
            print(f'error getting credentials from sts {sts_url}: {e}')
            sys.exit(1)

    def upload(self, local_path):
        storage = boto3.resource(
            's3',
            endpoint_url=self.config['host'],
            aws_access_key_id=self.config['access_key'],
            aws_secret_access_key=self.config['secret_key'],
            aws_session_token=self.config['session_token'],
            config=boto3.session.Config(signature_version=self.config['signature_version']),
            verify=self.config['verify']
        )
        storage.Bucket(self.config['bucket']).upload_file(local_path, basename(local_path))
