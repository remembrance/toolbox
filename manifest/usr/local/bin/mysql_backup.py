#!/usr/bin/env python

from os import getenv
from os.path import isfile

from kubectlme import MySQLBackup, S3Storage

host = getenv("MYSQL_HOST", "mysql")
user = getenv("MYSQL_USER", "backup")
password = getenv("MYSQL_PASS")
database = getenv("MYSQL_DB")
backup_dir = getenv("BACKUP_DIR", "/var/backup")
s3_url = getenv("S3_URL")
s3_user = getenv("S3_LDAP_USER")
s3_password = getenv("S3_LDAP_PASSWORD")
s3_bucket = getenv("S3_BUCKET")

backup = MySQLBackup(host, user, password, database)
file = backup.run()
if isfile(file):
    storage = S3Storage(s3_url, s3_bucket, s3_user, s3_password)
    storage.upload(file)
backup.cleanup()
