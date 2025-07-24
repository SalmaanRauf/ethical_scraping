"""
Error handling service for graceful degradation and comprehensive logging.
"""

import logging
import traceback
import time
from typing import Dict, Any, Optional, Callable
from functools import wraps
import asyncio

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ErrorHandler:
    """
    Centralized error handling service for the application.
    Provides graceful degradation, retry logic, and comprehensive logging.
    """
    
    def __init__(self):
        self.error_counts = {}
        self.performance_metrics = {}
        self.retry_config = {
            'max_retries': 3,
            'base_delay': 1.0,
            'max_delay': 30.0,
            'exponential_backoff': True
        }
    
    def handle_error(self, error: Exception, context: str, operation: str = None) -> Dict[str, Any]:
        """
        Handle an error with comprehensive logging and graceful degradation.
        
        Args:
            error: The exception that occurred
            context: Context where the error occurred
            operation: Specific operation that failed
            
        Returns:
            Dictionary with error information and recovery suggestions
        """
        error_key = f"{context}:{operation}" if operation else context
        
        # Increment error count
        if error_key not in self.error_counts:
            self.error_counts[error_key] = 0
        self.error_counts[error_key] += 1
        
        # Log error details
        logger.error(f"Error in {context} - {operation}: {str(error)}")
        logger.debug(f"Full traceback: {traceback.format_exc()}")
        
        # Determine error severity
        severity = self._determine_severity(error, self.error_counts[error_key])
        
        # Generate recovery suggestions
        recovery_suggestions = self._generate_recovery_suggestions(error, context, operation)
        
        return {
            'error': str(error),
            'context': context,
            'operation': operation,
            'severity': severity,
            'error_count': self.error_counts[error_key],
            'recovery_suggestions': recovery_suggestions,
            'timestamp': time.time()
        }
    
    def _determine_severity(self, error: Exception, error_count: int) -> str:
        """Determine error severity based on error type and frequency."""
        if error_count > 5:
            return 'critical'
        elif isinstance(error, (ConnectionError, TimeoutError)):
            return 'high'
        elif isinstance(error, ValueError):
            return 'medium'
        else:
            return 'low'
    
    def _generate_recovery_suggestions(self, error: Exception, context: str, operation: str) -> list:
        """Generate recovery suggestions based on error type and context."""
        suggestions = []
        
        if isinstance(error, ConnectionError):
            suggestions.append("Check network connectivity")
            suggestions.append("Verify API endpoints are accessible")
            suggestions.append("Consider retrying with exponential backoff")
        
        elif isinstance(error, TimeoutError):
            suggestions.append("Increase timeout settings")
            suggestions.append("Check system resources")
            suggestions.append("Consider reducing batch size")
        
        elif isinstance(error, ValueError):
            suggestions.append("Validate input data format")
            suggestions.append("Check data schema compliance")
            suggestions.append("Review data transformation logic")
        
        elif isinstance(error, KeyError):
            suggestions.append("Verify required fields are present")
            suggestions.append("Check data structure consistency")
            suggestions.append("Update data validation logic")
        
        else:
            suggestions.append("Review error logs for additional context")
            suggestions.append("Check system configuration")
            suggestions.append("Consider restarting the affected component")
        
        return suggestions
    
    def retry_operation(self, max_retries: int = None, base_delay: float = None):
        """
        Decorator for retrying operations with exponential backoff.
        
        Args:
            max_retries: Maximum number of retry attempts
            base_delay: Base delay between retries in seconds
        """
        def decorator(func: Callable):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                retries = max_retries or self.retry_config['max_retries']
                delay = base_delay or self.retry_config['base_delay']
                
                for attempt in range(retries + 1):
                    try:
                        return await func(*args, **kwargs)
                    except Exception as e:
                        if attempt == retries:
                            # Final attempt failed, log and raise
                            self.handle_error(e, f"{func.__name__}", "final_attempt")
                            raise
                        
                        # Log retry attempt
                        logger.warning(f"Attempt {attempt + 1} failed for {func.__name__}: {str(e)}")
                        
                        # Calculate delay with exponential backoff
                        current_delay = min(delay * (2 ** attempt), self.retry_config['max_delay'])
                        await asyncio.sleep(current_delay)
                
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                retries = max_retries or self.retry_config['max_retries']
                delay = base_delay or self.retry_config['base_delay']
                
                for attempt in range(retries + 1):
                    try:
                        return func(*args, **kwargs)
                    except Exception as e:
                        if attempt == retries:
                            # Final attempt failed, log and raise
                            self.handle_error(e, f"{func.__name__}", "final_attempt")
                            raise
                        
                        # Log retry attempt
                        logger.warning(f"Attempt {attempt + 1} failed for {func.__name__}: {str(e)}")
                        
                        # Calculate delay with exponential backoff
                        current_delay = min(delay * (2 ** attempt), self.retry_config['max_delay'])
                        time.sleep(current_delay)
                
                return None
            
            # Return appropriate wrapper based on function type
            if asyncio.iscoroutinefunction(func):
                return async_wrapper
            else:
                return sync_wrapper
        
        return decorator
    
    def track_performance(self, operation: str):
        """
        Decorator for tracking operation performance.
        
        Args:
            operation: Name of the operation being tracked
        """
        def decorator(func: Callable):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    result = await func(*args, **kwargs)
                    duration = time.time() - start_time
                    self._record_performance(operation, duration, success=True)
                    return result
                except Exception as e:
                    duration = time.time() - start_time
                    self._record_performance(operation, duration, success=False)
                    raise
            
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    result = func(*args, **kwargs)
                    duration = time.time() - start_time
                    self._record_performance(operation, duration, success=True)
                    return result
                except Exception as e:
                    duration = time.time() - start_time
                    self._record_performance(operation, duration, success=False)
                    raise
            
            # Return appropriate wrapper based on function type
            if asyncio.iscoroutinefunction(func):
                return async_wrapper
            else:
                return sync_wrapper
        
        return decorator
    
    def _record_performance(self, operation: str, duration: float, success: bool):
        """Record performance metrics for an operation."""
        if operation not in self.performance_metrics:
            self.performance_metrics[operation] = {
                'total_calls': 0,
                'successful_calls': 0,
                'failed_calls': 0,
                'total_duration': 0.0,
                'avg_duration': 0.0,
                'min_duration': float('inf'),
                'max_duration': 0.0
            }
        
        metrics = self.performance_metrics[operation]
        metrics['total_calls'] += 1
        metrics['total_duration'] += duration
        
        if success:
            metrics['successful_calls'] += 1
        else:
            metrics['failed_calls'] += 1
        
        # Update statistics
        metrics['avg_duration'] = metrics['total_duration'] / metrics['total_calls']
        metrics['min_duration'] = min(metrics['min_duration'], duration)
        metrics['max_duration'] = max(metrics['max_duration'], duration)
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get summary of performance metrics."""
        return {
            'error_counts': self.error_counts,
            'performance_metrics': self.performance_metrics,
            'total_errors': sum(self.error_counts.values()),
            'total_operations': sum(m['total_calls'] for m in self.performance_metrics.values())
        }
    
    def validate_json_response(self, response: str, context: str = "unknown") -> Optional[Dict]:
        """
        Validate and parse JSON response from LLM.
        
        Args:
            response: JSON string response
            context: Context for error reporting
            
        Returns:
            Parsed JSON dict or None if invalid
        """
        try:
            import json
            parsed = json.loads(response)
            return parsed
        except json.JSONDecodeError as e:
            self.handle_error(e, context, "json_parsing")
            return None
        except Exception as e:
            self.handle_error(e, context, "json_validation")
            return None

# Global error handler instance
error_handler = ErrorHandler()

def log_error(error: Exception, context: str):
    """
    Simple error logging function for backward compatibility.
    
    Args:
        error: The exception that occurred
        context: Context where the error occurred
    """
    error_handler.handle_error(error, context)
