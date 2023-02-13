
drop table if exists {schema}.on_run_hook;

create table {schema}.on_run_hook (
    "test_state"            STRING, -- start|end
    "target.dbname"    STRING,
    "target.host"      STRING,
    "target.name"      STRING,
    "target.schema"    STRING,
    "target.type"      STRING,
    "target.user"      STRING,
    "target.pass"      STRING,
    "target.threads"   INTEGER,

    "run_started_at"   STRING,
    "invocation_id"    STRING
);
