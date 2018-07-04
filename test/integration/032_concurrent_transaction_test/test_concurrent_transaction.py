from nose.plugins.attrib import attr
from test.integration.base import DBTIntegrationTest
import threading

class TestConcurrentTransaction(DBTIntegrationTest):

    def reset(self):
        self.query_state = {
            'view_model': 'wait',
            'model_1': 'wait',
        }

    @property
    def schema(self):
        return "concurrent_transaction_032"

    @property
    def models(self):
        return "test/integration/032_concurrent_transaction_test/models-table"

    @property
    def project_config(self):
        return {
            "macro-paths": ["test/integration/032_concurrent_transaction_test/macros"],
            "on-run-start": [
                "{{ create_udfs() }}",
            ],
        }

    def run_select_and_check(self, rel, sql):
        try:
            res = self.run_sql(sql, fetch='one')

            # The result is the output of f_sleep(), which is True
            if res[0] == True:
                self.query_state[rel] = 'good'
            else:
                self.query_state[rel] = 'bad'

        except Exception as e:
            if 'concurrent transaction' in str(e):
                self.query_state[rel] = 'error: {}'.format(e)
            else:
                self.query_state[rel] = 'error: {}'.format(e)

    def async_select(self, rel, sleep=10):
        # Run the select statement in a thread. When the query returns, the global
        # query_state will be update with a state of good/bad/error, and the associated
        # error will be reported if one was raised.

        schema = self.unique_schema()
        query = '''
        -- async_select: {rel}
        select {schema}.f_sleep({sleep}) from {schema}.{rel}
        '''.format(
                schema=schema,
                sleep=sleep,
                rel=rel)

        thread = threading.Thread(target=lambda: self.run_select_and_check(rel, query))
        thread.start()
        return thread

    def run_test(self):
        self.use_profile("redshift")

        # First run the project to make sure the models exist
        self.run_dbt(args=['run'])

        # Execute long-running queries in threads
        t1 = self.async_select('view_model', 10)
        t2 = self.async_select('model_1', 5)

        # While the queries are executing, re-run the project
        res = self.run_dbt(args=['run', '--threads', '8'])

        # Finally, wait for these threads to finish
        t1.join()
        t2.join()

        self.assertTrue(len(res) > 0)

        # If the query succeeded, the global query_state should be 'good'
        self.assertEqual(self.query_state['view_model'], 'good')
        self.assertEqual(self.query_state['model_1'], 'good')

    @attr(type="redshift")
    def test__redshift__concurrent_transaction_table(self):
        self.use_default_project({
            "model-paths": ["test/integration/032_concurrent_transaction_test/models-table"],
        })
        self.reset()
        self.run_test()

    @attr(type="redshift")
    def test__redshift__concurrent_transaction_view(self):
        self.use_default_project({
            "model-paths": ["test/integration/032_concurrent_transaction_test/models-view"],
        })
        self.reset()
        self.run_test()

    @attr(type="redshift")
    def test__redshift__concurrent_transaction_incremental(self):
        self.use_default_project({
            "model-paths": ["test/integration/032_concurrent_transaction_test/models-incremental"],
        })
        self.reset()
        self.run_test()
