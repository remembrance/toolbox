#!/usr/bin/env python

# simple mysqldump and upload to minio/s3

import storage
import os.path
import time
import sys
from subprocess import run, CalledProcessError, check_output, DEVNULL, PIPE

class MySQLBackup:
    def __init__(self):
        self.config = {}
        self.config['host'] = os.getenv('MYSQL_HOST', 'mysql')
        self.config['user'] = os.getenv('MYSQL_USER', 'backup')
        self.config['password'] = os.getenv('MYSQL_PASS')
        self.config['db'] = os.getenv('MYSQL_DB')
        self.config['backup_dir'] = os.getenv('BACKUP_DIR', '/var/backup')

        for i in self.config.keys():
            if not self.config[i]:
                raise OSError(2, f'missing required config key or environment variable "{i}" proceed')

        self.files = []

    def create_backup(self):
        def create_my_cnf(path, host, user, password):
            try:
                with open(path, 'w') as cnf:
                    cnf.write('\n'.join([
                        '[mysqldump]',
                        f'host={host}',
                        f'user={user}',
                        f'password={password}',
                        'verbose=TRUE',
                        'single-transaction=TRUE'
                        ]))
            except IOError as e:
                print(f'error creating my.cnf file for mysqldump: {e}')

        def invalid_db_name(name):
            return any(not (c.isalnum() or c == "_") for c in name)

        my_cnf = os.path.join(self.config['backup_dir'], '.my.cnf')
        create_my_cnf(my_cnf, self.config['host'], self.config['user'], self.config['password'])
        self.files.append(my_cnf)

        db = self.config['db']
        if invalid_db_name(db):
            print(f'error: db name {db} seems invalid')
            self.cleanup()
            sys.exit(1)

        date = int(time.time())
        my_backup = os.path.join(self.config['backup_dir'], f'{db}_{date}.sql.gz')
        self.files.append(my_backup)
        dump = [f'mysqldump --defaults-file={my_cnf} {db} | gzip -9 > {my_backup}']
        proc = run(dump, stderr=PIPE, shell=True)
        print(proc.stderr.decode('utf-8'))
        if proc.returncode != 0:
            self.cleanup()
            sys.exit(1)

        return my_backup

    def cleanup(self):
        for i in self.files:
            try:
                print(f'removing file {i}')
                os.remove(i)
            except IOError:
                pass

    def run(self):
        backup_path = self.create_backup()
        if backup_path:
            store = storage.S3Storage()
            store.upload(backup_path)
        self.cleanup()


if __name__ == '__main__':
    backup = MySQLBackup()
    backup.run()
