# Notes on converting tests from unittest to pytest

* Base fixtures are provided in the tests/functional/conftest.py file
* You can override any fixture by specifying it in your test script
* You can't use any test utility from the legacy tests that starts with 'self'.
* Most special case assert functions will work with a simple 'assert'
* Every integration test needs to use the 'project' fixture
* Files are not copied (unless done explicitly in the test) so if you need
  to access a local file (like seed.sql) you need to get the path from the project fixture,
  (project.data_dir) or the 'data_dir' fixture (for specifying the location of data files.
  Default is the test\_dir).
* Table comparison methods have been moved to TableComparison in test/tables.py
* Fixtures are for test setup, and are specified in the test signature. You can't call
  fixtures in the middle of a test function.
* Information from the fixture setup that might be needed later in the test is provided
  by the project fixture return class (TestProjInfo)
* Every fixture has a scope, which means that you can call it multiple times in the
  same scope and it will return the same thing
* All fixtures are run before and after the test function they're attached to.
  If you have teardown pieces in the fixture, do a 'yield' after the setup, and
  the part after the 'yield' will be run at teardown.
* 'run\_dbt', 'run\_sql', and 'get\_manifest' are provided by the tests/util.py file
* You will probably want to make separate test files out of tests that use
  substantially different projects. If they're only different by a file or two,
  you could write out individual files instead and keep them in the same file.
* You can also import file strings from other test cases
* old: self.get\_models\_in\_schema, new: get\_tables\_in\_schema
* somewhat easier way to get the legacy files into a more usable format:
  ```tail -n +1 models/* > copy_models.out```
* some of the legacy tests used a 'default_project' method to change (for example)
  the seeds directory to load a different seed. Don't do that. Copying a file is
  probably a better option.


# Integration test directories that have been converted
* 003\_simple\_reference\_tests
* 001\_simple\_copy\_tests (except TestQuoteDatabase)
