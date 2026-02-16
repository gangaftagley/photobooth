#!/usr/bin/env python3
"""printer.py -- Robust CUPS printing with error handling and retry logic."""

import cups
import time
import logging

logger = logging.getLogger('photobooth.printer')

# CUPS job state constants (from cups.h)
JOB_PENDING = 3
JOB_HELD = 4
JOB_PROCESSING = 5
JOB_STOPPED = 6
JOB_CANCELED = 7
JOB_ABORTED = 8
JOB_COMPLETED = 9

FAILED_STATES = {JOB_CANCELED, JOB_ABORTED, JOB_STOPPED, JOB_HELD}


class PrintError(Exception):
    """Raised when printing fails after all retries."""
    pass


class Printer:
    def __init__(self, max_retries=3, retry_delay=5):
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._conn = None
        self._printer_name = None

    def is_available(self):
        """Check if a local (USB) printer is connected and reachable. Returns True/False."""
        try:
            conn = cups.Connection()
            printers = conn.getPrinters()
            if not printers:
                return False

            # Only use local printers (USB, serial, parallel) — skip network printers
            for name, props in printers.items():
                uri = props.get('device-uri', '')
                if uri.startswith(('usb://', 'serial:', 'parallel:')):
                    self._conn = conn
                    self._printer_name = name
                    logger.info("Local printer found: %s (%s)", name, uri)
                    return True

            logger.warning("No local printers found (network printers ignored)")
            return False
        except Exception as e:
            logger.warning("No printer available: %s", e)
            return False

    def _connect(self):
        """Get or create a CUPS connection. Reconnects if stale."""
        try:
            if self._conn:
                self._conn.getPrinters()
                return self._conn
        except Exception:
            self._conn = None

        self._conn = cups.Connection()
        printers = self._conn.getPrinters()
        if not printers:
            raise PrintError("No printers found")
        self._printer_name = next(iter(printers.keys()))
        logger.info("Connected to printer: %s", self._printer_name)
        return self._conn

    def get_printer_status(self):
        """Query printer state. Returns dict with name, state, state_message, accepting."""
        conn = self._connect()
        printers = conn.getPrinters()
        info = printers[self._printer_name]
        return {
            'name': self._printer_name,
            'state': info.get('printer-state', 0),
            'state_message': info.get('printer-state-message', ''),
            'accepting': info.get('printer-is-accepting-jobs', False),
        }

    def clear_failed_jobs(self):
        """Cancel any stuck/held/stopped jobs. Returns count cleared."""
        conn = self._connect()
        jobs = conn.getJobs(which_jobs='not-completed')
        cleared = 0
        for job_id, job_info in jobs.items():
            state = job_info.get('job-state', 0)
            if state in FAILED_STATES:
                try:
                    conn.cancelJob(job_id)
                    cleared += 1
                    logger.info("Cleared failed job %d (state=%d)", job_id, state)
                except Exception as e:
                    logger.warning("Could not cancel job %d: %s", job_id, e)
        return cleared

    def _wait_for_job(self, job_id, timeout=120):
        """
        Poll job status until it completes or fails.
        Returns True if job completed successfully, False otherwise.
        """
        conn = self._connect()
        start = time.time()
        poll_interval = 2

        while time.time() - start < timeout:
            try:
                jobs = conn.getJobs(which_jobs='all')
                if job_id not in jobs:
                    logger.info("Job %d no longer in queue (assumed completed)", job_id)
                    return True

                state = jobs[job_id].get('job-state', 0)

                if state == JOB_COMPLETED:
                    logger.info("Job %d completed successfully", job_id)
                    return True
                elif state in FAILED_STATES:
                    msg = jobs[job_id].get('job-state-message', 'unknown')
                    logger.warning("Job %d failed: state=%d msg=%s", job_id, state, msg)
                    if state == JOB_HELD:
                        try:
                            conn.setJobHoldUntil(job_id, 'no-hold')
                            logger.info("Resumed held job %d", job_id)
                            time.sleep(poll_interval)
                            continue
                        except Exception:
                            pass
                    return False
                else:
                    logger.debug("Job %d state=%d, waiting...", job_id, state)

            except Exception as e:
                logger.warning("Error polling job %d: %s", job_id, e)
                self._conn = None

            time.sleep(poll_interval)

        logger.error("Job %d timed out after %ds", job_id, timeout)
        return False

    def print_file(self, filepath, on_status=None):
        """
        Print a file with retry logic.

        Args:
            filepath: absolute path to the image file
            on_status: optional callback(message: str) for display updates

        Returns:
            True if print succeeded, False if all retries exhausted.
        """
        def status(msg):
            logger.info(msg)
            if on_status:
                on_status(msg)

        self.clear_failed_jobs()

        for attempt in range(1, self.max_retries + 1):
            try:
                status("Printing... (%d/%d)" % (attempt, self.max_retries))
                conn = self._connect()

                # Check if printer is stopped and try to re-enable
                printer_status = self.get_printer_status()
                if printer_status['state'] == 5:  # stopped
                    status("Printer stopped, re-enabling...")
                    try:
                        conn.enablePrinter(self._printer_name)
                        conn.acceptJobs(self._printer_name)
                        time.sleep(2)
                    except Exception as e:
                        logger.warning("Could not re-enable printer: %s", e)

                job_id = conn.printFile(
                    self._printer_name, filepath, "PhotoBooth", {}
                )
                status("Printing...")

                if self._wait_for_job(job_id):
                    status("Print complete!")
                    return True
                else:
                    status("Print attempt %d failed" % attempt)
                    try:
                        conn.cancelJob(job_id)
                    except Exception:
                        pass

            except Exception as e:
                status("Print error: %s" % e)
                self._conn = None

            if attempt < self.max_retries:
                status("Retrying in %ds..." % self.retry_delay)
                time.sleep(self.retry_delay)

        status("Printing failed!")
        return False

    def check_paper_status(self):
        """Check printer status message for paper-related errors."""
        try:
            status = self.get_printer_status()
            msg = status['state_message'].lower()
            if 'paper' in msg or 'media' in msg:
                return False
        except Exception:
            pass
        return True
