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
from datetime import datetime, timedelta
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
            # Clear cached next run time when setting up new schedule
            if 'cached_next_run' in config:
                del config['cached_next_run']
                self.save_schedules(self.get_all_schedule_configs())
            
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
    
    def calculate_next_run_time(self, site):
        """Calculate next run time based on schedule config"""
        try:
            config = self.get_schedule_config(site)
            if not config:
                logger.warning(f"No config found for site {site}")
                return None
            
            # Check if we already have a cached next run time that's still valid
            cached_next_run = config.get('cached_next_run')
            if cached_next_run:
                try:
                    cached_time = datetime.fromisoformat(cached_next_run)
                    # If cached time is still in the future, use it
                    if cached_time > datetime.now(VN_TZ):
                        logger.info(f"Using cached next run time for {site}: {cached_time}")
                        return cached_time
                except (ValueError, TypeError):
                    pass
            
            now = datetime.now(VN_TZ)
            schedule_type = config.get('schedule_type')
            schedule_time = config.get('schedule_time')
            schedule_day = config.get('schedule_day')
            custom_interval = config.get('custom_interval')
            custom_unit = config.get('custom_unit')
            
            logger.info(f"Calculating next run for {site}: type={schedule_type}, interval={custom_interval}, unit={custom_unit}")
            
            if schedule_type == "minute":
                # Next minute
                next_run = now.replace(second=0, microsecond=0) + timedelta(minutes=1)
                self._cache_next_run_time(site, next_run)
                return next_run
                
            elif schedule_type == "hourly":
                # Next hour at specified minute
                if schedule_time and ':' in schedule_time:
                    minute = int(schedule_time.split(':')[1])
                    next_run = now.replace(minute=minute, second=0, microsecond=0)
                    if next_run <= now:
                        next_run += timedelta(hours=1)
                    self._cache_next_run_time(site, next_run)
                    return next_run
                else:
                    # Default: next hour
                    next_run = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
                    self._cache_next_run_time(site, next_run)
                    return next_run
                    
            elif schedule_type == "daily":
                # Next day at specified time
                if schedule_time and ':' in schedule_time:
                    hour, minute = map(int, schedule_time.split(':'))
                    next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    if next_run <= now:
                        next_run += timedelta(days=1)
                    self._cache_next_run_time(site, next_run)
                    return next_run
                else:
                    # Default: tomorrow at same time
                    next_run = now + timedelta(days=1)
                    self._cache_next_run_time(site, next_run)
                    return next_run
                    
            elif schedule_type == "weekly":
                # Next week on specified day at specified time
                if schedule_day and schedule_time and ':' in schedule_time:
                    hour, minute = map(int, schedule_time.split(':'))
                    # Map day names to numbers (Monday=0, Sunday=6)
                    day_map = {
                        'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
                        'friday': 4, 'saturday': 5, 'sunday': 6
                    }
                    target_day = day_map.get(schedule_day.lower(), 0)
                    current_day = now.weekday()
                    days_ahead = (target_day - current_day) % 7
                    if days_ahead == 0:  # Same day
                        next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                        if next_run <= now:
                            days_ahead = 7  # Next week
                    if days_ahead > 0:
                        next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0) + timedelta(days=days_ahead)
                        self._cache_next_run_time(site, next_run)
                        return next_run
                else:
                    # Default: next week same day
                    next_run = now + timedelta(weeks=1)
                    self._cache_next_run_time(site, next_run)
                    return next_run
                    
            elif schedule_type == "custom" and custom_interval and custom_unit:
                # Custom interval
                logger.info(f"Processing custom schedule: interval={custom_interval}, unit={custom_unit}")
                unit_map = {
                    "phút": "minutes", "giờ": "hours", 
                    "ngày": "days", "tuần": "weeks"
                }
                unit_en = unit_map.get(custom_unit, "hours")
                logger.info(f"Mapped unit: {custom_unit} -> {unit_en}")
                
                if unit_en == "minutes":
                    next_run = now + timedelta(minutes=custom_interval)
                elif unit_en == "hours":
                    next_run = now + timedelta(hours=custom_interval)
                elif unit_en == "days":
                    next_run = now + timedelta(days=custom_interval)
                elif unit_en == "weeks":
                    next_run = now + timedelta(weeks=custom_interval)
                else:
                    next_run = now + timedelta(hours=custom_interval)
                
                logger.info(f"Calculated next run: {next_run}")
                # Cache the calculated time
                self._cache_next_run_time(site, next_run)
                return next_run
            
            return None
            
        except Exception as e:
            logger.error(f"Error calculating next run time for {site}: {e}")
            return None
    
    def _cache_next_run_time(self, site, next_run_time):
        """Cache the next run time for a site"""
        try:
            configs = self.get_all_schedule_configs()
            if site in configs:
                configs[site]['cached_next_run'] = next_run_time.isoformat()
                self.save_schedules(configs)
                logger.info(f"Cached next run time for {site}: {next_run_time}")
        except Exception as e:
            logger.error(f"Error caching next run time for {site}: {e}")
    
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

