import dbt.clients.system
import logging
import os
import sys
import re

import colorama

# disable logs from other modules, excepting CRITICAL logs
logging.getLogger('botocore').setLevel(logging.CRITICAL)
logging.getLogger('contracts').setLevel(logging.CRITICAL)
logging.getLogger('requests').setLevel(logging.CRITICAL)
logging.getLogger('urllib3').setLevel(logging.CRITICAL)
logging.getLogger('snowflake.connector').setLevel(logging.CRITICAL)


# Colorama needs some help on windows because we're using logger.info
# intead of print(). If the Windows env doesn't have a TERM var set,
# then we should override the logging stream to use the colorama
# converter. If the TERM var is set (as with Git Bash), then it's safe
# to send escape characters and no log handler injection is needed.
colorama_stdout = sys.stdout
colorama_wrap = True

if sys.platform == 'win32' and not os.environ.get('TERM'):
    colorama_wrap = False
    colorama_stdout = colorama.AnsiToWin32(sys.stdout).stream

elif sys.platform == 'win32':
    colorama_wrap = False

colorama.init(wrap=colorama_wrap)

# create a global console logger for dbt
stdout_handler = logging.StreamHandler(colorama_stdout)
stdout_handler.setFormatter(logging.Formatter('%(message)s'))
stdout_handler.setLevel(logging.INFO)

logger = logging.getLogger()
logger.addHandler(stdout_handler)
logger.setLevel(logging.DEBUG)

initialized = False


def make_log_dir_if_missing(log_dir):
    dbt.clients.system.make_directory(log_dir)


class ColorFilter:
    color_regexp = re.compile(r'\x1b\[[\d;]+m')

    @classmethod
    def filter(cls, line):
        subbed = re.sub(cls.color_regexp, '', line.msg)
        line.msg = subbed
        return True


def initialize_logger(debug_mode=False, path=None):
    global initialized, logger, stdout_handler

    if initialized:
        return

    if debug_mode:
        stdout_handler.setFormatter(
            logging.Formatter('%(asctime)-18s: %(message)s'))
        stdout_handler.setLevel(logging.DEBUG)

    if path is not None:
        make_log_dir_if_missing(path)
        log_path = os.path.join(path, 'dbt.log')

        # log to directory as well
        logdir_handler = logging.handlers.TimedRotatingFileHandler(
            filename=log_path,
            when='d',
            interval=1,
            backupCount=7,
        )

        logdir_handler.addFilter(ColorFilter)

        logdir_handler.setFormatter(
            logging.Formatter('%(asctime)-18s: %(message)s'))
        logdir_handler.setLevel(logging.DEBUG)

        logger.addHandler(logdir_handler)

    initialized = True


GLOBAL_LOGGER = logger
