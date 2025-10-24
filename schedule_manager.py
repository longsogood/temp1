"""
Persistent Schedule Manager
Quản lý lịch test tự động độc lập với Streamlit session
"""
import json
import os
import schedule
import threading
import time
import logging
from datetime import datetime
import pytz

# Setup logging
logger = logging.getLogger(__name__)

SCHEDULE_CONFIG_FILE = "schedule_config.json"
VN_TZ = pytz.timezone('Asia/Ho_Chi_Minh')


class ScheduleManager:
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self.schedule_thread = None
        self.running = False
        self._initialized = True
        
        # Load existing schedules
        self.load_schedules()
        
        # Start schedule manager thread
        self.start()
    
    def load_schedules(self):
        """Load schedules from JSON file"""
        if not os.path.exists(SCHEDULE_CONFIG_FILE):
            logger.info("No schedule config file found, creating new one")
            self.save_schedules({})
            return
        
        try:
            with open(SCHEDULE_CONFIG_FILE, 'r', encoding='utf-8') as f:
                configs = json.load(f)
            
            logger.info(f"Loaded {len(configs)} schedule configs")
            
            # Setup schedules from config
            for site, config in configs.items():
                if config is not None:
                    self._setup_schedule_from_config(site, config)
                    
        except Exception as e:
            logger.error(f"Error loading schedules: {e}")
    
    def save_schedules(self, configs):
        """Save schedules to JSON file"""
        try:
            with open(SCHEDULE_CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(configs, f, indent=2, ensure_ascii=False)
            logger.info("Saved schedule configs")
        except Exception as e:
            logger.error(f"Error saving schedules: {e}")
    
    def get_schedule_config(self, site):
        """Get schedule config for a site"""
        try:
            if os.path.exists(SCHEDULE_CONFIG_FILE):
                with open(SCHEDULE_CONFIG_FILE, 'r', encoding='utf-8') as f:
                    configs = json.load(f)
                return configs.get(site)
        except Exception as e:
            logger.error(f"Error getting schedule config for {site}: {e}")
        return None
    
    def update_schedule(self, site, config):
        """Update schedule for a site"""
        try:
            # Load current configs
            if os.path.exists(SCHEDULE_CONFIG_FILE):
                with open(SCHEDULE_CONFIG_FILE, 'r', encoding='utf-8') as f:
                    configs = json.load(f)
            else:
                configs = {}
            
            # Remove old schedule for this site
            self.remove_schedule(site)
            
            # Update config
            configs[site] = config
            self.save_schedules(configs)
            
            # Setup new schedule
            if config is not None:
                self._setup_schedule_from_config(site, config)
            
            logger.info(f"Updated schedule for site: {site}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating schedule for {site}: {e}")
            return False
    
    def remove_schedule(self, site):
        """Remove schedule for a site"""
        try:
            # Find and cancel jobs for this site
            jobs_to_remove = []
            for job in schedule.jobs:
                try:
                    # Check if job belongs to this site
                    if len(job.job_func.args) >= 3 and job.job_func.args[2] == site:
                        jobs_to_remove.append(job)
                except (IndexError, AttributeError):
                    continue
            
            for job in jobs_to_remove:
                schedule.cancel_job(job)
            
            logger.info(f"Removed {len(jobs_to_remove)} jobs for site: {site}")
            
            # Update config file
            if os.path.exists(SCHEDULE_CONFIG_FILE):
                with open(SCHEDULE_CONFIG_FILE, 'r', encoding='utf-8') as f:
                    configs = json.load(f)
                configs[site] = None
                self.save_schedules(configs)
            
            return True
            
        except Exception as e:
            logger.error(f"Error removing schedule for {site}: {e}")
            return False
    
    def _setup_schedule_from_config(self, site, config):
        """Setup schedule from config"""
        try:
            # Import dynamically để tránh circular dependency
            import importlib
            import sys
            
            # Determine which site module to use
            if site == "THFC":
                module_name = "pages.THFC"
            else:
                module_name = "pages.Agent HR Nội bộ"
            
            # Import module và get run_scheduled_test function
            if module_name in sys.modules:
                module = sys.modules[module_name]
            else:
                module = importlib.import_module(module_name)
            
            run_scheduled_test = getattr(module, 'run_scheduled_test', None)
            if run_scheduled_test is None:
                logger.error(f"run_scheduled_test function not found in {module_name}")
                return
            
            file_path = config['file_path']
            schedule_type = config['schedule_type']
            schedule_time = config.get('schedule_time')
            schedule_day = config.get('schedule_day')
            test_name = config['test_name']
            api_url = config.get('api_url', 'https://site1.com')
            evaluate_api_url = config.get('evaluate_api_url', 'https://site2.com')
            custom_interval = config.get('custom_interval')
            custom_unit = config.get('custom_unit')
            
            # Setup schedule based on type
            if schedule_type == "minute":
                schedule.every().minute.do(
                    run_scheduled_test,
                    file_path, test_name, site, api_url, evaluate_api_url
                )
            
            elif schedule_type == "hourly":
                minute = schedule_time.split(':')[1]
                schedule.every().hour.at(f":{minute}").do(
                    run_scheduled_test,
                    file_path, test_name, site, api_url, evaluate_api_url
                )
            
            elif schedule_type == "daily":
                schedule.every().day.at(schedule_time).do(
                    run_scheduled_test,
                    file_path, test_name, site, api_url, evaluate_api_url
                )
            
            elif schedule_type == "weekly":
                day = schedule_day.lower()
                getattr(schedule.every(), day).at(schedule_time).do(
                    run_scheduled_test,
                    file_path, test_name, site, api_url, evaluate_api_url
                )
            
            elif schedule_type == "custom" and custom_interval and custom_unit:
                unit_map = {"phút": "minutes", "giờ": "hours", "ngày": "days", "tuần": "weeks"}
                unit_en = unit_map.get(custom_unit, "hours")
                getattr(schedule.every(custom_interval), unit_en).do(
                    run_scheduled_test,
                    file_path, test_name, site, api_url, evaluate_api_url
                )
            
            logger.info(f"Setup schedule for {site}: {schedule_type}")
            
        except Exception as e:
            logger.error(f"Error setting up schedule from config: {e}")
    
    def get_next_run(self, site):
        """Get next run time for a site's schedule"""
        try:
            for job in schedule.jobs:
                try:
                    if len(job.job_func.args) >= 3 and job.job_func.args[2] == site:
                        if job.next_run:
                            # Convert to Vietnam timezone
                            next_run_utc = pytz.utc.localize(job.next_run)
                            next_run_vn = next_run_utc.astimezone(VN_TZ)
                            return next_run_vn
                except (IndexError, AttributeError):
                    continue
        except Exception as e:
            logger.error(f"Error getting next run for {site}: {e}")
        return None
    
    def start(self):
        """Start the schedule manager thread"""
        if self.running:
            logger.warning("Schedule manager already running")
            return
        
        self.running = True
        self.schedule_thread = threading.Thread(target=self._run_schedule, daemon=True)
        self.schedule_thread.start()
        logger.info("Schedule manager started")
    
    def stop(self):
        """Stop the schedule manager thread"""
        self.running = False
        if self.schedule_thread:
            self.schedule_thread.join(timeout=5)
        logger.info("Schedule manager stopped")
    
    def _run_schedule(self):
        """Run the schedule loop"""
        logger.info("Schedule loop started")
        while self.running:
            try:
                schedule.run_pending()
                time.sleep(1)
            except Exception as e:
                logger.error(f"Error in schedule loop: {e}")
                time.sleep(5)  # Wait before retry
        logger.info("Schedule loop stopped")
    
    def get_all_jobs(self):
        """Get all scheduled jobs with details"""
        jobs_info = []
        for job in schedule.jobs:
            try:
                if len(job.job_func.args) >= 3:
                    site = job.job_func.args[2]
                    test_name = job.job_func.args[1]
                    next_run = None
                    if job.next_run:
                        next_run_utc = pytz.utc.localize(job.next_run)
                        next_run = next_run_utc.astimezone(VN_TZ)
                    
                    jobs_info.append({
                        'site': site,
                        'test_name': test_name,
                        'next_run': next_run
                    })
            except (IndexError, AttributeError):
                continue
        return jobs_info


# Global instance
_schedule_manager = None

def get_schedule_manager():
    """Get or create schedule manager singleton"""
    global _schedule_manager
    if _schedule_manager is None:
        _schedule_manager = ScheduleManager()
    return _schedule_manager

