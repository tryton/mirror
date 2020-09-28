import os
import cmd
import shlex
import subprocess
import getpass
import io
import configparser

import hgapi
import requests
from github import Github, UnknownObjectException

# The repositories that need to be mirrored.
# The format:
#
#  ('relative path of tryton repo', 'git_repo_name')
REPOS = [
    ('trytond', 'trytond'),
    ('tryton', 'tryton'),
    ('proteus', 'proteus'),
    ('sao', 'sao'),
    ('cookiecutter', 'cookiecutter-tryton'),
    ('chronos', 'chronos'),
    ('trytond-gis', 'trytond-gis'),
]

# Canonical source base_url
HG_BASE_URL = 'https://hg.tryton.org'

# The directory where the mercurial repos should be cloned to
HG_CACHE = 'hg'

# The directory where git repositories should be cached
GIT_CACHE = 'git'

# additional git remotes. A provision to set the remotes other than the
# default github remote
ADDITIONAL_REMOTES = {
    # module: [list, of, remotes]
}


class CommandHandler(cmd.Cmd):

    def do_setup(self, line=None):
        """
        Setup the cache folders

        * Setup cache folders
        * Setup empty git repos for each module
        """
        if not os.path.exists(HG_CACHE):
            os.makedirs(HG_CACHE)
        if not os.path.exists(GIT_CACHE):
            os.makedirs(GIT_CACHE)

        for hg_module, git_name in REPOS:
            git_repo_dir = os.path.join(GIT_CACHE, git_name)
            if not os.path.exists(git_repo_dir):
                subprocess.check_call(
                    shlex.split('git init -q %s' % git_repo_dir))

    def do_clone_all(self, line=None):
        """
        Clone all hg repos
        """
        for hg_module, git_name in REPOS:
            if os.path.exists(os.path.join(HG_CACHE, hg_module)):
                continue

            repo_url = '/'.join([HG_BASE_URL, hg_module])
            cmd = 'hg clone -q %s %s/%s' % (
                repo_url, HG_CACHE, hg_module,
            )
            subprocess.check_call(shlex.split(cmd))

            hgrc = os.path.join('.', HG_CACHE, hg_module, '.hg/hgrc')

            config = configparser.ConfigParser()
            config.readfp(open(hgrc))

            # Set the configuration for extensions and bookmarks
            if 'extensions' not in config.sections():
                config.add_section('extensions')
            config.set('extensions', 'hgext.bookmarks', '')
            config.set('extensions', 'hggit', '')

            # Setting for using named branches
            # https://github.com/schacon/hg-git#gitbranch_bookmark_suffix
            if 'git' not in config.sections():
                config.add_section('git')
            config.set('git', 'branch_bookmark_suffix', '_bookmark')

            with open(hgrc, 'wb') as configfile:
                config.write(configfile)

    def do_pull_all(self, line=None):
        """
        Pull all repos one by one
        """
        for hg_module, git_name in REPOS:
            subprocess.check_call(
                shlex.split('hg --cwd %s pull -u -q' %
                    os.path.join(HG_CACHE, hg_module))
                )

    def _make_bookmarks(self, repo):
        """
        Create bookmarks for each repo
        """
        for branch in repo.get_branch_names():
            bookmark = '%s_bookmark' % branch
            if branch == 'default':
                bookmark = 'develop_bookmark'
            repo.hg_command('bookmark', '-f', '-r', branch, bookmark)

    def do_hg_to_git(self, line=None):
        """
        Move from hg to local git repo
        """
        for hg_module, git_name in REPOS:
            hg_repo = hgapi.Repo(os.path.join(HG_CACHE, hg_module))
            self._make_bookmarks(hg_repo)
            cmd = shlex.split('hg --cwd=%s push -q %s' % (
                    os.path.join(HG_CACHE, hg_module),
                    os.path.abspath(os.path.join(GIT_CACHE, git_name))
                    ))
            retcode = subprocess.call(cmd)
            if retcode not in [0, 1]:
                raise subprocess.CalledProcessError(retcode, cmd)

    def _get_default_remote(self, git_name):
        return "git@github.com:tryton/%s.git" % git_name

    def do_push_to_remotes(self, line=None):
        """
        Push the code to the remotes in a git repository
        """
        for hg_module, git_name in REPOS:
            remotes = [self._get_default_remote(git_name)]
            remotes.extend(ADDITIONAL_REMOTES.get('git_name', []))
            for remote in remotes:
                subprocess.check_call(
                    shlex.split(
                        'git --git-dir=%s/%s/.git push -q --mirror %s' % (
                            GIT_CACHE, git_name, remote)))


class RepoHandler(object):

    github_client = None

    @staticmethod
    def get_tryton_module_names():
        rv = requests.get('https://downloads.tryton.org/modules.txt')
        return rv.text.splitlines()

    def get_github_client(self):
        """
        Return an authenticated github client
        """
        if self.github_client:
            return self.github_client

        self.github_client = Github(
            io.open(os.path.expanduser(
                    os.path.join('~', '.config', 'mirror_token'))
                ).read().strip())
        return self.github_client

    def is_repo_on_github(self, repo_name):
        github_client = self.get_github_client()
        try:
            github_client.get_repo('tryton/%s' % repo_name)
        except UnknownObjectException:
            return False
        else:
            return True

    @staticmethod
    def has_branch(repo, name):
        for branch in repo.get_branches():
            if branch.name == name:
                return True
        return False

    def create_repo(self, repo_name, homepage=None):
        github_client = self.get_github_client()
        tryton_org = github_client.get_organization('tryton')
        return tryton_org.create_repo(repo_name, 'Mirror of %s' % repo_name,
            homepage=homepage, has_wiki=False, has_issues=False)

    def create_missing_repos(self):
        repos = {g for r, g in REPOS}
        repos.update(self.get_tryton_module_names())
        git2hg = {git_name: hg_module for hg_module, git_name in REPOS}

        github_client = self.get_github_client()
        tryton_org = github_client.get_organization('tryton')
        org_repos = {r.name: r for r in tryton_org.get_repos()}
        for repo_name in repos:
            homepage = '/'.join([HG_BASE_URL, git2hg[repo_name]])
            repo = org_repos.get(repo_name)
            if not repo:
                self.create_repo(repo_name, homepage)
                org_repos[repo_name] = repo
            elif (repo.has_wiki or repo.has_issues or repo.homepage != homepage
                    or (repo.default_branch != 'develop'
                        and self.has_branch(repo, 'develop'))):
                repo.edit(repo_name, homepage=homepage,
                    has_wiki=False, has_issues=False, default_branch='develop')

# Add the modules from tryton module list
for module_name in RepoHandler.get_tryton_module_names():
    REPOS.append(('modules/%s' % module_name, module_name))


if __name__ == '__main__':
    CommandHandler().cmdloop()
