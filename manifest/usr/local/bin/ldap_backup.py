#!/usr/bin/env python3

import gzip
from datetime import datetime as dt
from os import getenv, remove
from os.path import isfile, join

from kubectlme import ContainerCommand, S3Storage

selector = getenv("POD_SELECTOR")
namespace = getenv("K8S_NAMESPACE")
container = getenv("CONTAINER_NAME")
s3_url = getenv("S3_URL")
s3_user = getenv("S3_LDAP_USER")
s3_password = getenv("S3_LDAP_PASSWORD")
s3_bucket = getenv("S3_BUCKET")

backup_dir = "/tmp"
openldap_conf_dir = "/opt/bitnami/openldap/etc/slapd.d"
timestamp = dt.strftime(dt.now(), "%Y-%m-%d-%H-%M-%S")
data_backup_file = ""
cfg_backup_file = ""

data = ContainerCommand(
    selector, namespace, container, f"slapcat -n 2 -F {openldap_conf_dir}"
).run()
if data:
    data_backup_file = f"ldap_backup_{timestamp}.ldif.gz"
    with gzip.open(f"{join(backup_dir, data_backup_file)}", "wb") as f:
        f.write(data)

cfg = ContainerCommand(
    selector, namespace, container, f"slapcat -b cn=config -F {openldap_conf_dir}"
).run()
if cfg:
    cfg_backup_file = f"ldap_cfg_backup_{timestamp}.ldif.gz"
    with gzip.open(f"{join(backup_dir, cfg_backup_file)}", "wb") as f:
        f.write(cfg)

storage = S3Storage(s3_url, s3_bucket, s3_user, s3_password)
if isfile(data_backup_file):
    storage.upload(data_backup_file)
    remove(data_backup_file)
if isfile(cfg_backup_file):
    storage.upload(cfg_backup_file)
    remove(cfg_backup_file)
