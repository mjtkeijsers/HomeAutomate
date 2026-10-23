#!/usr/bin/env python3
"""Run each configured scheduled task once for a test pass."""

from functools import partial
import time

import schedule

from HomeAutCommon import logger

def run_test_tasks():
    """Run each distinct scheduled task once, pausing briefly between tasks."""
    scheduled_tasks = []
    seen_tasks = set()
    for job in schedule.get_jobs():
        task = job.job_func
        if isinstance(task, partial):
            task = task.func
        if task not in seen_tasks:
            scheduled_tasks.append(task)
            seen_tasks.add(task)

    logger.info("Running each scheduled task once in test mode...")

    for index, task in enumerate(scheduled_tasks):
        if index:
            time.sleep(1)
        logger.info(f"Test run: {task.__name__}")
        task()
