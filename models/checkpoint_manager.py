"""
Checkpoint management for the crawler to support incremental processing.
"""

import os
import json
import asyncio
import time
from datetime import datetime
from typing import List, Dict, Any, Optional

from loguru import logger
from config import Config


class CheckpointManager:
    """
    Manages checkpoints for incremental crawling, evaluation, and results saving.
    """

    def __init__(
        self,
        run_id: str,
        output_dir: str = "outputs",
        checkpoint_interval: int = 60,
        min_batch_size: int = 10,
        max_batch_size: int = 30,
    ):
        """
        Initialize the checkpoint manager.

        Args:
            run_id: Unique identifier for this crawler run
            output_dir: Directory to save checkpoints
            checkpoint_interval: Time between checkpoints in seconds
            min_batch_size: Minimum application pages to trigger batch processing
            max_batch_size: Maximum batch size for evaluation
        """
        self.run_id = run_id
        self.checkpoint_dir = os.path.join(output_dir, "checkpoints", run_id)
        self.checkpoint_interval = checkpoint_interval
        self.min_batch_size = min_batch_size
        self.max_batch_size = max_batch_size

        # Create checkpoint directory
        os.makedirs(self.checkpoint_dir, exist_ok=True)

        # Track state
        self.last_checkpoint_time = time.time()
        self.pending_applications = []
        self.evaluated_applications = []
        self.lock = asyncio.Lock()

        # Create run info file
        self._save_run_info()

        logger.info(f"Checkpoint manager initialized for run {run_id}")
        logger.info(f"Checkpoints will be saved to {self.checkpoint_dir}")

    def _save_run_info(self):
        """Save basic run information to help with recovery."""
        info = {
            "run_id": self.run_id,
            "start_time": datetime.now().isoformat(),
            "checkpoint_interval": self.checkpoint_interval,
            "min_batch_size": self.min_batch_size,
            "max_batch_size": self.max_batch_size,
            "config": {
                "model": Config.MODEL_NAME,
                "max_depth": Config.MAX_DEPTH,
                "max_urls": Config.MAX_TOTAL_URLS,
                "workers": Config.NUM_WORKERS,
            },
        }

        with open(os.path.join(self.checkpoint_dir, "run_info.json"), "w") as f:
            json.dump(info, f, indent=2)

    async def add_application_page(self, page: Dict[str, Any]) -> bool:
        """
        Add an application page to the pending queue.

        Returns:
            bool: True if checkpoint processing was triggered
        """
        async with self.lock:
            self.pending_applications.append(page)

            # Check if we should process a batch
            return await self.should_process_batch()

    async def should_process_batch(self) -> bool:
        """
        Check if we should process a batch of applications.

        Returns:
            bool: True if we should process a batch
        """
        # Check if we have enough pages and enough time has passed
        if len(self.pending_applications) >= self.min_batch_size:
            if len(self.pending_applications) >= self.max_batch_size:
                logger.info(
                    f"Checkpoint triggered: reached max batch size ({self.max_batch_size})"
                )
                return True

            if time.time() - self.last_checkpoint_time >= self.checkpoint_interval:
                logger.info(
                    f"Checkpoint triggered: interval reached ({self.checkpoint_interval}s)"
                )
                return True

        return False

    async def get_batch_for_processing(self) -> List[Dict[str, Any]]:
        """
        Get a batch of application pages for processing.

        Returns:
            List of application pages to process
        """
        async with self.lock:
            # Get up to max_batch_size pages
            batch_size = min(len(self.pending_applications), self.max_batch_size)
            if batch_size == 0:
                return []

            batch = self.pending_applications[:batch_size]

            # Remove the batch from pending applications
            self.pending_applications = self.pending_applications[batch_size:]

            # Update checkpoint time
            self.last_checkpoint_time = time.time()

            return batch

    async def add_evaluated_applications(self, applications: List[Dict[str, Any]]):
        """Add evaluated application pages."""
        async with self.lock:
            self.evaluated_applications.extend(applications)

            # Save the checkpoint
            await self.save_checkpoint()

    async def save_checkpoint(self):
        """Save the current state to a checkpoint file."""
        try:
            # Create a timestamp for the checkpoint
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            # Save pending applications
            if self.pending_applications:
                with open(
                    os.path.join(self.checkpoint_dir, f"pending_{timestamp}.json"), "w"
                ) as f:
                    json.dump(self.pending_applications, f)

            # Save evaluated applications
            if self.evaluated_applications:
                # Save the latest batch
                with open(
                    os.path.join(self.checkpoint_dir, f"evaluated_{timestamp}.json"),
                    "w",
                ) as f:
                    json.dump(self.evaluated_applications, f)

                # Save cumulative results
                with open(
                    os.path.join(self.checkpoint_dir, "evaluated_all.json"), "w"
                ) as f:
                    json.dump(self.evaluated_applications, f)

                # Generate a new checkpoint report
                try:
                    from output.how_to_apply_report import generate_how_to_apply_report

                    report_file = os.path.join(
                        self.checkpoint_dir, f"how_to_apply_{timestamp}.md"
                    )
                    generate_how_to_apply_report(
                        self.evaluated_applications, report_file, detailed=False
                    )
                    logger.info(f"Generated checkpoint report: {report_file}")
                except Exception as e:
                    logger.warning(f"Could not generate checkpoint report: {e}")

            logger.success(f"Saved checkpoint at {timestamp}")

            return timestamp
        except Exception as e:
            logger.error(f"Error saving checkpoint: {e}")
            return None

    async def save_crawler_state(self, state_manager):
        """
        Save the current crawler state for possible resume.

        Args:
            state_manager: The crawler's state manager instance
        """
        try:
            # Get state data to save
            counters = await state_manager.get_counters()
            domain_counts = await state_manager.get_domain_counts()
            admission_domains = await state_manager.get_admission_domains()

            # Create state object
            state = {
                "timestamp": datetime.now().isoformat(),
                "counters": counters,
                "domain_counts": domain_counts,
                "admission_domains": list(admission_domains),
            }

            # Save state to file
            with open(
                os.path.join(self.checkpoint_dir, "crawler_state.json"), "w"
            ) as f:
                json.dump(state, f, indent=2)

            logger.debug("Saved crawler state")
        except Exception as e:
            logger.error(f"Error saving crawler state: {e}")

    def get_all_evaluated_applications(self) -> List[Dict[str, Any]]:
        """Get all evaluated applications."""
        return self.evaluated_applications

    def get_stats(self) -> Dict[str, Any]:
        """Get checkpoint stats."""
        return {
            "pending_applications": len(self.pending_applications),
            "evaluated_applications": len(self.evaluated_applications),
            "last_checkpoint_time": self.last_checkpoint_time,
            "time_since_checkpoint": time.time() - self.last_checkpoint_time,
        }
