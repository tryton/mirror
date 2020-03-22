Tryton - mercurial to git mirror
================================

This package provides a wrapper around the hg-git library to mirror the
tryton repositories to github.
It uses the access token stored in `~/.config/mirror_token`.


Using through CLI
-----------------

It is possible to interact with the toolkit using the CLI bundled with
this application.::

    $ tryton_mirror

You can type `help` to see the list of commands available.

Using a cron to perform the tasks
---------------------------------

A cron script which does all the required steps is also provided.

You can add a line like the one below to your crontab to execute this
periodically.::


    cd /path/to/cache/folder && tryton_mirror_sync

.. note::

    The repo cache directories are (re)created in the current working
    directory. Therefore navigating to the folder before executing the
    command is very important.


I want to set this up on my own
-------------------------------

To begin with, you can use the same mirroring to your private repos with
probably a limited number of modules. Whatever the need may be, you can
start by subclassing the CommandHandler class.


Adding a new repository
-----------------------

1. Create a new repo for the same on github.
2. Add a line to the repos list.
