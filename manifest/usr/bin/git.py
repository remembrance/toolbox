#!/usr/bin/env python3

import random
import string
import sys
from json import dumps
from os import fsync, makedirs
from os.path import basename, dirname, exists, join
from shutil import rmtree
from typing import Union

from pygit2 import (
    GIT_RESET_HARD,
    GitError,
    Keypair,
    RemoteCallbacks,
    Repository,
    Signature,
    clone_repository,
    discover_repository,
)


class GitRepo:
    def __init__(self, repoUrl, branch, pubKey, privKey, password):
        self.repo = None
        self.branch = branch
        self.repoTmpPath = "/var/tmp"

        if not exists(pubKey) or not exists(privKey):
            raise GitError

        keypair = Keypair("git", pubKey, privKey, password)

        self.cb = RemoteCallbacks(credentials=keypair)
        self.repoPath = join(self.repoTmpPath, f"{basename(repoUrl)}.git")

        if exists(self.repoPath):
            try:
                print(f"discovering existing repo: {self.repoPath}")
                _repoPath = discover_repository(self.repoPath)
                self.repo = Repository(_repoPath)
                if self.repo.is_bare:
                    raise GitError

                for i, r in enumerate(self.repo.remotes):
                    if r.name == "origin":
                        self.repo.remotes[i].fetch(
                            [f"refs/remotes/origin/{self.branch}"], callbacks=self.cb
                        )

                for b in list(self.repo.branches.remote):
                    if b == f"origin/{self.branch}":
                        branch = self.repo.branches.get(b)
                        assert branch is not None
                        ref = branch.target.hex
                        print(f"hard resetting to origin/{self.branch}: {ref}")
                        self.repo.reset(ref, GIT_RESET_HARD)

            except GitError:
                print("error discovering repo, removing and stopping script")
                rmtree(self.repoPath)
                sys.exit(1)

        else:
            print(f"cloning repository: {repoUrl}")
            self.repo = clone_repository(
                f"ssh://git@{repoUrl}", self.repoPath, callbacks=self.cb
            )

    def get_branch_name(self):
        assert self.repo is not None
        branch_names = list(
            set(
                [
                    basename(x)
                    for x in list(self.repo.branches.local)
                    + list(self.repo.branches.remote)
                ]
            )
        )
        letters = string.ascii_lowercase + string.digits
        while True:
            branch = "automation-{}".format(
                "".join(random.choice(letters) for i in range(3))
            )
            if branch in branch_names:
                continue
            else:
                return branch

    def write_json(self, content, repo_file_path, topic):
        assert self.repo is not None
        _path = join(self.repo.workdir, dirname(repo_file_path))
        if _path != self.repo.workdir and not exists(_path):
            makedirs(_path, 0o755)

        with open(join(self.repo.workdir, repo_file_path), "w") as fp:
            fp.write(dumps(content))
            fp.flush()
            fsync(fp.fileno())
            fp.close()
            self.commit_push_file(repo_file_path, topic)

    def commit_push_file(self, repo_file_path, topic):
        assert self.repo is not None
        try:
            ref = self.repo.head.name
            parents = [self.repo.head.target]
            index = self.repo.index
            index.add_all()
            index.write()
            user = Signature("Automation Bot", "automation@bln.space")
            message = f"chore(update): {topic} {repo_file_path}"
            tree = index.write_tree()
            self.repo.create_commit(ref, user, user, message, tree, parents)
            self.repo.index.write()

            branch_name = self.get_branch_name()
            target = self.repo.branches.get(f"{self.branch}").target
            commit = self.repo.revparse_single(target.hex)
            print(f"creating new branch {branch_name} with commit {commit.id}")
            branch = self.repo.branches.local.create(branch_name, commit)
            self.repo.checkout(f"refs/heads/{branch_name}")

            for i, r in enumerate(self.repo.remotes):
                if r.name == "origin":
                    print(f"pushing to origin/{branch_name}")
                    self.repo.remotes[i].push(
                        [f"refs/heads/{branch_name}:refs/heads/{branch_name}"],
                        callbacks=self.cb,
                    )

            self.repo.checkout(f"refs/heads/{self.branch}")
            self.repo.branches.delete(branch_name)

        except GitError as e:
            print(f"error executing git operation during commit/push: {e}")


if __name__ == "__main__":
    # git = GitRepo('github.com/gutmensch/argocd', 'id_automation.pub', 'id_automation', 'xW4SwtPtZLwwfJ7EECCn')
    git = GitRepo(
        "github.com/gutmensch/pygit-test",
        "main",
        "id_automation.pub",
        "id_automation",
        "xW4SwtPtZLwwfJ7EECCn",
    )
    git.write_json(
        {"foo": "bar", "boo": "baz"}, "bla/test/foo/bar/fritzbox.json", "dyndns update"
    )
