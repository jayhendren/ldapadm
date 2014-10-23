## Python 2 project skeleton

This is a skeleton Python 2 project.

### How to use this skeleton

1. Clone this repository and give the project a new name (and new upstream repository).
2. From the command line, run `bin/watch`.
3. In another window, open your favorite text editor and start hacking.  The `watch` script will automatically run the unit tests for your project whenever a file in your project is updated so that you can follow along as your tests fail and pass.

### Contents of this project

* `src`: Contains the source code for the modules this project will export.
* `tests`: contains unit tests written using Python's [`unittest`](https://docs.python.org/2/library/unittest.html) module.  The default `unittest` behavior is to run tests in files of the naming scheme `test*.py`, and the files must be importable as modules from the root directory of the project.  (Strictly speaking, tests do not need to live in only the `tests` directory.)
* `bin/watch`: A Python script that sets a watch on your project and runs the test suite whenever a file in your project is updated.  Requires the [`watchdog`](http://pythonhosted.org/watchdog/index.html) package.  This script may be run from anywhere, but the script itself expects to be located in a direct subdirectory of the project root.
* `conf/watch.conf.yaml`: A YAML-formatted document that contains configuration for the `watch` script.  The following values may (and must) be set:
  * `cooldown_period`: Amount of time, in seconds, between subsequent runs of the testing suite.  Since text editors may write multiple files at once, or the same file multiple times in a short period, this is to prevent the tests from running multiple times despite updating a file once.
  * `paths`: A list of paths, relative to the root directory of this project, containing files to watch.
  * `patterns`: A list of patterns to match against filenames.  This is passed directly to `watchdog`'s `PatternMatchingEventHandler`.  It's not entirely clear what rules `watchdog` uses for pattern matching; I've only had success with the standard glob (`*`) operator so far (e.g. `*.py`).
  * `test_cmd`: The command that will run the testing suite.
