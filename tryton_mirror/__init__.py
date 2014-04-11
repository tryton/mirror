import os
import re
import cmd
import getpass
import ConfigParser

import envoy
import hgapi
import requests
from bs4 import BeautifulSoup
from github import Github, UnknownObjectException

# The repositories that need to be mirrored.
# The format:
#
#  ('relative path of tryton repo', 'git_repo_name')
REPOS = [
    ('trytond', 'trytond'),
    ('tryton', 'tryton'),
    ('proteus', 'proteus'),
    ('neso', 'neso'),

    # Selected sandbox modules
    ('sandbox/sao', 'sao'),

]

# Canonical source base_url
HG_BASE_URL = 'http://hg.tryton.org'

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
                envoy.run('git init %s' % git_repo_dir)

    def do_clone_all(self, line=None):
        """
        Clone all hg repos
        """
        for hg_module, git_name in REPOS:
            print "Setup: %s" % hg_module
            if os.path.exists(os.path.join(HG_CACHE, hg_module)):
                print "%s is already setup. Continue" % hg_module
                continue

            repo_url = '/'.join([HG_BASE_URL, hg_module])
            print "Clone repo"
            r = envoy.run('hg clone %s %s/%s' % (
                repo_url, HG_CACHE, hg_module,
            ))
            print r.std_out
            print r.std_err
            hgrc = os.path.join(HG_CACHE, hg_module, '.hg/hgrc')

            config = ConfigParser.ConfigParser()
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
            envoy.run('hg --cwd %s pull -u' % os.path.join(HG_CACHE, hg_module))

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
            r = envoy.run(
                'hg --cwd=%s push %s' % (
                    os.path.join(HG_CACHE, hg_module),
                    os.path.abspath(os.path.join(GIT_CACHE, git_name))
                )
            )
            print r.std_out
            print r.std_err

    def _get_default_remote(self, git_name):
        return "git@github.com:tryton/%s.git" % git_name

    def do_push_to_remotes(self, line=None):
        """
        Push the code to the remotes in a git repository
        """
        for hg_module, git_name in REPOS:
            print "Pushing %s to remotes" % hg_module
            remotes = [self._get_default_remote(git_name)]
            remotes.extend(ADDITIONAL_REMOTES.get('git_name', []))
            for remote in remotes:
                print "Remote: %s" % remote
                r = envoy.run(
                    'git --git-dir=%s/%s/.git push --all %s' % (
                        GIT_CACHE, git_name, remote
                    )
                )
                print r.std_out
                print r.std_err


class RepoHandler(object):

    github_client = None

    @staticmethod
    def get_tryton_module_names():
        rv = requests.get('http://hg.tryton.org/modules/?sort=name')
        html = BeautifulSoup(rv.content)
        return [
            row.td.text
            for row in html.body.find_all('tr')[1:]
        ]

    def get_github_client(self):
        """
        Return an authenticated github client
        """
        if self.github_client:
            return self.github_client

        self.github_client = Github("tryton-mirror", getpass.getpass())
        return self.github_client

    def is_repo_on_github(self, repo_name):
        github_client = self.get_github_client()
        try:
            github_client.get_repo('tryton/%s' % repo_name)
        except UnknownObjectException:
            return False
        else:
            return True

    def create_repo(self, repo_name):
        github_client = self.get_github_client()
        tryton_org = github_client.get_organization('tryton')
        return tryton_org.create_repo(repo_name, 'Mirror of %s' % repo_name)

    def create_missing_repos(self):
        repos = ['trytond', 'tryton', 'neso', 'proteus']
        repos.extend(self.get_tryton_module_names())

        github_client = self.get_github_client()
        tryton_org = github_client.get_organization('tryton')
        org_repos = [r.name for r in tryton_org.get_repos()]
        for repo in repos:
            if repo not in org_repos:
                print "Create repo: %s" % repo
                self.create_repo(repo)


# Add the modules from tryton module list
for module_name in RepoHandler.get_tryton_module_names():
    REPOS.append(('modules/%s' % module_name, module_name))


if __name__ == '__main__':
    CommandHandler().cmdloop()
