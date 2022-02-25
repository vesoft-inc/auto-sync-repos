#!/usr/bin/env python3

import os
import re
import sh
import time

from pathlib import Path
from github import Github
from dingtalkchatbot.chatbot import DingtalkChatbot
from sh import git


dingtalk_access_token = os.environ["INPUT_DINGTALK_ACCESS_TOKEN"]
dingtalk_secret = os.environ["INPUT_DINGTALK_SECRET"]
enable_dingtalk_notification = len(dingtalk_access_token) > 0 and len(dingtalk_secret) > 0
dingtalk_bot = DingtalkChatbot(
    webhook=f"https://oapi.dingtalk.com/robot/send?access_token={dingtalk_access_token}",
    secret=dingtalk_secret,
)

gh_url = "https://github.com"

token = os.environ['INPUT_REPO_TOKEN']
gh = Github(token)

prog = re.compile(r"(.*)\(#(\d+)\)(?:$|\n).*")
title_re = re.compile(r"(.*)(?:$|\n).*")


class Commit:
    def __init__(self, commit = None):
        self.commit = commit
        self.title = None
        self.pr_num = -1
        self.extract_pr_num_and_title(commit)

    def author(self):
        assert self.is_valid()
        return self.commit.commit.author

    def login(self):
        assert self.is_valid()
        return self.commit.author.login

    def is_valid(self):
        return self.commit is not None and (self.pr_num >= 0 or self.title is not None)

    def has_same_title(self, ci):
        return self.title.lower() == ci.title.lower()

    def extract_pr_num_and_title(self, commit):
        if commit is None:
            return
        msg = prog.match(commit.commit.message)
        if msg:
            self.pr_num = int(msg.group(2))
            while msg:
                self.title = msg.group(1).strip()
                msg = prog.match(self.title)
        else:
            msg = title_re.match(commit.commit.message)
            if msg:
                self.title = msg.group(1).strip()


def get_org_members(org_name):
    print(">>> Get org members")
    org = gh.get_organization(org_name)
    return [m.login for m in org.get_members()]


def must_create_dir(filename):
    dirname = os.path.dirname(filename)
    if len(dirname) > 0 and not os.path.exists(dirname):
        sh.mkdir('-p', dirname)


def overwrite_conflict_files(ci):
    print(">>> Overwrite PR conflict files")
    for f in ci.files:
        if f.status == "removed" and os.path.exists(f.filename):
            git.rm('-rf', f.filename)
        else:
            must_create_dir(f.filename)
            sh.curl("-fsSL", f.raw_url, "-o", f.filename)
        print(f"      {f.filename}")


def commit_changes(ci: Commit):
    author = ci.author()
    print(f">>> Commit changes by <{author.email}>")
    git.add(".")
    git.commit("-m", ci.title, "--author", f"{author.name} <{author.email}>")


def conflict_file_list(lines):
    prefix = "CONFLICT (content): Merge conflict in "
    return [l[len(prefix):] for l in lines if l.startswith(prefix)]


def apply_patch(branch, comm_ci):
    print(f">>> Apply patch file to {branch}")
    stopped = False
    author = comm_ci.author()
    git.config("--local", "user.name", author.name)
    git.config("--local", "user.email", author.email)
    git.clean("-f")
    git.fetch("origin", "master")
    git.checkout("-b", branch, "origin/master")
    git_commit = comm_ci.commit
    conflict_files = []
    try:
        git('cherry-pick', git_commit.sha)
    except Exception as e:
        err = str(e)
        print(">>> Fail to apply the patch to branch {}, cause: {}".format(branch, err))
        if err.find('more, please see e.stdout') >= 0 and isinstance(e, sh.ErrorReturnCode):
            ee = sh.ErrorReturnCode(e)
            print(">>> DEBUG: stdout of ErrorReturnCode: {}".format(ee.stdout))
            conflict_files = conflict_file_list(ee.stdout)
        else:
            conflict_files = conflict_file_list(err.splitlines())
        git('cherry-pick', '--abort')
        overwrite_conflict_files(git_commit)
        commit_changes(comm_ci)
        stopped = True

    try:
        git.push("-u", "origin", branch)
    except Exception as e:
        print(">>> Fail to push branch({}) to origin, caused by {}".format(branch, e))

    return (stopped, conflict_files)


def find_latest_community_commit_in_ent_repo(ent_commit: Commit, community_commits):
    assert ent_commit.is_valid()
    for ci in community_commits:
        assert ci.is_valid()
        if ent_commit.has_same_title(ci):
            user = gh.get_user().login
            if ent_commit.login() == user:
                return ci
            else:
                print(">>> [WARN] the commit has been checkin by {} rather than {}: {}".format(ent_commit.login(), user, ent_commit.title))
    return Commit()


def generate_latest_100_commits(repo):
    commits = []
    for i, ci in enumerate(repo.get_commits()):
        if i > 100:
            break
        commit = Commit(repo.get_commit(ci.sha))
        if commit.is_valid():
            commits.append(commit)
    return commits


def find_unmerged_community_commits_in_ent_repo(community_repo, ent_repo):
    ent_commits = generate_latest_100_commits(ent_repo)
    community_commits = generate_latest_100_commits(community_repo)
    for ent_commit in ent_commits:
        ci = find_latest_community_commit_in_ent_repo(ent_commit, community_commits)
        if ci.is_valid():
            return community_commits[:community_commits.index(ci)]
    return []


def pr_ref(repo, pr):
    pr_num = pr if isinstance(pr, int) else pr.number
    if pr_num >= 0:
        return "{}#{}".format(repo.full_name, pr_num)
    return repo.full_name


def pr_link(repo, pr):
    pr_num = pr if isinstance(pr, int) else pr.number
    return "[{}]({}/{}/pull/{})".format(pr_ref(repo, pr_num), gh_url, repo.full_name, pr_num)


def co_authored_by(author):
    return "Co-authored-by: {} <{}>".format(author.name, author.email)


def append_migration_in_msg(repo, ci, pr):
    body = pr.body if pr.body else ""
    coauthor = co_authored_by(ci.author())
    return "{}\n\nMigrated from {}\n\n{}\n".format(body, pr_ref(repo, pr), coauthor)


def notify_author_by_comment(ent_repo, comm_repo, comm_ci, issue_num, comm_pr_num, org_members, conflict_files):
    comment = ""
    if comm_ci.login() in org_members:
        comment += f"@{comm_ci.login()}\n"
        print(f">>> Notify the author by comment: {comm_ci.login()}")
    else:
        print(f">>> The author {comm_ci.login()} is not in the orgnization, need not to notify him")

    comment += """This PR will cause conflicts when applying patch.
Please carefully compare all the changes in this PR to avoid overwriting legal codes.
If you need to make changes, please make the commits on current branch.

You can use following commands to resolve the conflicts locally:

```shell
$ git clone git@github.com:{}.git
$ cd {}
$ git checkout -b pr-{} origin/master
$ git remote add community git@github.com:{}.git
$ git fetch community master
$ git cherry-pick {}
# resolve the conflicts
$ git cherry-pick --continue
$ git push -f origin pr-{}
```

CONFLICT FILES:
```text
{}
```
"""

    issue = ent_repo.get_issue(issue_num)
    issue.create_comment(comment.format(ent_repo.full_name,
                                        ent_repo.name,
                                        comm_pr_num,
                                        comm_repo.full_name,
                                        comm_ci.commit.sha,
                                        comm_pr_num,
                                        '\n'.join(conflict_files)))


def create_pr(comm_repo, ent_repo, comm_ci, org_members):
    try:
        merged_pr = comm_repo.get_pull(comm_ci.pr_num)
        branch = "pr-{}".format(merged_pr.number)
        stopped, conflict_files = apply_patch(branch, comm_ci)
        body = append_migration_in_msg(comm_repo, comm_ci, merged_pr)
        new_pr = ent_repo.create_pull(title=comm_ci.title, body=body, head=branch, base="master")

        print(f">>> Create PR: {pr_ref(ent_repo, new_pr)}")
        time.sleep(2)

        new_pr = ent_repo.get_pull(new_pr.number)
        new_pr.add_to_labels('auto-sync')

        if stopped:
            notify_author_by_comment(ent_repo,
                                     comm_repo,
                                     comm_ci,
                                     new_pr.number,
                                     comm_ci.pr_num,
                                     org_members,
                                     conflict_files)
            return (False, new_pr.number)

        if not new_pr.mergeable:
            return (False, new_pr.number)

        commit_title = "{} (#{})".format(comm_ci.title, new_pr.number)
        status = new_pr.merge(merge_method='squash', commit_title=commit_title)
        if not status.merged:
            return (False, new_pr.number)
        return (True, new_pr.number)
    except Exception as e:
        print(">>> Fail to merge PR {}, cause: {}".format(comm_ci.pr_num, e))
        return (False, -1 if new_pr is None else new_pr.number)


def get_org_name(repo):
    l = repo.split('/')
    assert len(l) == 2
    return l[0]


def get_repo_name(repo):
    l = repo.split('/')
    assert len(l) == 2
    return l[1]


def add_community_upstream(comm_repo):
    remote_url = 'https://github.com/{}.git'.format(comm_repo.full_name)
    remote_name = 'community'

    try:
        git.remote('-vv')
        git.remote('rm', remote_name)
    except:
        print(">>> The remote upstream({}) not found.".format(remote_name))

    try:
        git.remote('add', remote_name, remote_url)
        git.fetch(remote_name, 'master')
    except Exception as e:
        print(">>> Fail to add remote, cause: {}".format(e))
        raise


def main(community_repo, enterprise_repo):
    comm_repo = gh.get_repo(community_repo)
    ent_repo = gh.get_repo(enterprise_repo)

    org_members = get_org_members(get_org_name(community_repo))

    unmerged_community_commits = find_unmerged_community_commits_in_ent_repo(comm_repo, ent_repo)
    unmerged_community_commits.reverse()

    add_community_upstream(comm_repo)

    succ_pr_list = []
    err_pr_list = []
    for ci in unmerged_community_commits:
        res = create_pr(comm_repo, ent_repo, ci, org_members)
        md = pr_link(comm_repo, ci.pr_num)
        if res[1] >= 0:
            md += " -> " + pr_link(ent_repo, res[1])
        md += " " + ci.login()
        if res[0]:
            succ_pr_list.append(md)
            print(f">>> {pr_ref(ent_repo, res[1])} has been migrated from {pr_ref(comm_repo, ci.pr_num)}")
        else:
            err_pr_list.append(md)
            print(f">>> {pr_ref(comm_repo, ci.pr_num)} could not be merged into {pr_ref(ent_repo, res[1])}")
            break

    succ_prs = '\n\n'.join(succ_pr_list) if succ_pr_list else "None"
    err_prs = '\n\n'.join(err_pr_list) if err_pr_list else "None"

    print(">>> Enable dingtalk notification: {}".format(enable_dingtalk_notification))
    if enable_dingtalk_notification and (len(succ_pr_list) > 0 or len(err_pr_list) > 0):
        text = f"### Auto Merge Status\nMerge successfully:\n\n{succ_prs}\n\nFailed to merge:\n\n{err_prs}"
        dingtalk_bot.send_markdown(title='Auto Merge Status', text=text, is_at_all=False)

    if len(unmerged_community_commits) == 0:
        print(">>> There's no any PRs to sync")


if __name__ == "__main__":
    src_repo = os.environ["INPUT_FROM_REPO"]
    target_repo = os.environ["GITHUB_REPOSITORY"]

    main(src_repo, target_repo)
