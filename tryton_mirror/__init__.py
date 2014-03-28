import os
import cmd
import ConfigParser

import envoy
import hgapi

# The repositories that need to be mirrored.
# The format:
#
#  ('relative path of tryton repo', 'git_repo_name')
REPOS = [
    ('trytond', 'trytond'),
    ('tryton', 'tryton'),
    ('modules/party', 'party'),
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
                    'git --git-dir=%s/%s/.git push %s' % (
                        GIT_CACHE, git_name, remote
                    )
                )
                print r.std_out
                print r.std_err


if __name__ == '__main__':
    CommandHandler().cmdloop()
