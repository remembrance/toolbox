"""
library with helper classes for kubernetes features/workload management
(c) Robert Schumann <rs@kubectl.me>
License: MIT
"""

import datetime as dt
import os
import os.path
import sys
import xml.dom.minidom as _xml
from os.path import basename
from subprocess import PIPE, run
from sys import exit, stderr
from urllib.error import HTTPError, URLError

import boto3
from kubernetes import client, config, stream


class MySQLBackup:
    def __init__(self, host, user, password, db, dir="/var/backup"):
        if None in [host, user, password, db]:
            raise ValueError("init of MySQLBackup failed with missing variables")

        self.host = host
        self.user = user
        self.password = password
        self.db = db
        self.dir = dir
        self.files = []

    def create_backup(self):
        def create_my_cnf(path, host, user, password):
            try:
                with open(path, "w") as cnf:
                    cnf.write(
                        "\n".join(
                            [
                                "[mysqldump]",
                                f"host={host}",
                                f"user={user}",
                                f"password={password}",
                                "verbose=TRUE",
                                "single-transaction=TRUE",
                            ]
                        )
                    )
            except IOError as e:
                print(f"error creating my.cnf file for mysqldump: {e}")

        def invalid_db_name(name):
            return any(not (c.isalnum() or c == "_") for c in name)

        my_cnf = os.path.join(self.dir, ".my.cnf")
        create_my_cnf(my_cnf, self.host, self.user, self.password)
        self.files.append(my_cnf)

        if invalid_db_name(self.db):
            print(f"error: db name {self.db} seems invalid")
            self.cleanup()
            sys.exit(1)

        date = dt.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        my_backup = os.path.join(self.dir, f"{self.db}_{date}.sql.gz")
        self.files.append(my_backup)
        dump = [f"mysqldump --defaults-file={my_cnf} {self.db} | gzip -9 > {my_backup}"]
        proc = run(dump, stderr=PIPE, shell=True)
        print(proc.stderr.decode("utf-8"))
        if proc.returncode != 0:
            self.cleanup()
            sys.exit(1)

        return my_backup

    def cleanup(self):
        for i in self.files:
            try:
                print(f"removing file {i}")
                os.remove(i)
            except IOError:
                pass

    def run(self):
        backup_path = self.create_backup()
        if backup_path:
            return backup_path


class STSCredentials(object):
    def __init__(self, url, user, password):
        if None in [url, user, password]:
            raise ValueError("init of STSCredentials failed with missing variables")
        self.stsUrl = url
        self.ldapUser = user
        self.ldapPassword = password

    def retrieve(self):
        def get(dom, key):
            try:
                result = dom.getElementsByTagName("AssumeRoleWithLDAPIdentityResult")[0]
                creds = result.getElementsByTagName("Credentials")[0]
                return creds.getElementsByTagName(key)[0].firstChild.nodeValue
            except IndexError as e:
                print(f"error accessing response key {key}: {e}", file=stderr)

        from urllib import parse, request

        payload = {
            "Action": "AssumeRoleWithLDAPIdentity",
            "LDAPUsername": self.ldapUser,
            "LDAPPassword": self.ldapPassword,
            "Version": "2011-06-15",
            "Duration": "3600",
        }
        data = parse.urlencode(payload).encode()
        req = request.Request(self.stsUrl, data=data, method="POST")
        try:
            with request.urlopen(req) as resp:
                with _xml.parseString(resp.read()) as dom:
                    assert (
                        dom.documentElement.tagName
                        == "AssumeRoleWithLDAPIdentityResponse"
                    )
                    return (
                        get(dom, "AccessKeyId"),
                        get(dom, "SecretAccessKey"),
                        get(dom, "SessionToken"),
                    )

        except HTTPError as e:
            print(
                f"error communicating with {self.stsUrl}: {e.read().decode()}",
                file=stderr,
            )
        except URLError as e:
            print(f"error getting credentials from sts {self.stsUrl}: {e}", file=stderr)

        return (None, None, None)


class S3Storage(object):
    # using OpenLDAP credentials
    def __init__(self, host, bucket, user, password, version="s3v4", verify=False):
        if None in [host, bucket, user, password]:
            raise ValueError("init of S3Storage failed with missing variables")

        self.host = host
        self.bucket = bucket
        self.user = user
        self.password = password
        self.signature_version = version
        self.verify = verify
        self.credentials = STSCredentials(self.host, self.user, self.password)
        (
            self.access_key,
            self.secret_key,
            self.session_token,
        ) = self.credentials.retrieve()

        if None in [self.access_key, self.secret_key, self.session_token]:
            raise ValueError("could not acquire s3 credentials through sts")

    def upload(self, local_path):
        storage = boto3.resource(
            "s3",
            endpoint_url=self.host,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            aws_session_token=self.session_token,
            config=boto3.session.Config(signature_version=self.signature_version),
            verify=self.verify,
        )
        storage.Bucket(self.bucket).upload_file(local_path, basename(local_path))


class ContainerCommand(object):
    def __init__(self, selector, namespace, name, command):
        if None in [selector, namespace, name, command]:
            raise ValueError("init variables missing for ContainerCommand")

        try:
            config.load_incluster_config()
        except config.ConfigException as e:
            print(e, file=stderr)
            exit(10)

        try:
            self.k8s = client.CoreV1Api()
        except client.ApiException as e:
            print(e, file=stderr)
            exit(11)

        self.selector = selector
        self.namespace = namespace
        self.name = name
        self.command = command

    def run(self):
        try:
            resp = self.k8s.list_namespaced_pod(
                namespace=self.namespace, label_selector=self.selector
            )

            pods = [x.spec.hostname for x in resp.items if x.spec.hostname]
            if not pods:
                raise RuntimeError("no pod for command detected")

            for name in pods:
                print(f"running command in pod {name}", file=stderr)
                resp = self.k8s.read_namespaced_pod(name=name, namespace=self.namespace)

                exec_command = [
                    "/bin/sh",
                    "-c",
                    self.command,
                ]

                self.output = stream.stream(
                    self.k8s.connect_get_namespaced_pod_exec,
                    name,
                    self.namespace,
                    container=self.name,
                    command=exec_command,
                    stderr=False,
                    stdin=False,
                    stdout=True,
                    tty=False,
                )

                if self.output:
                    return self.output.encode("utf-8")

        except client.ApiException as e:
            print(e, file=stderr)
            exit(12)
