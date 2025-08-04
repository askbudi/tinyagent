#!/usr/bin/env python3
"""
Test to demonstrate the kwargs issue.
"""

import asyncio
import logging

logging.basicConfig(level=logging.DEBUG, format='%(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_kwargs_issue():
    """Demonstrate the kwargs passing issue."""
    
    # Original data
    original_data = {"messages": [{"role": "user", "created_at": 12345}]}
    logger.info(f"Original data: {original_data}")
    
    async def modify_kwargs(**kwargs):
        logger.info(f"Inside function - kwargs before: {kwargs}")
        # Modify kwargs
        kwargs["messages"] = [{"role": "user"}]  # Remove created_at
        logger.info(f"Inside function - kwargs after: {kwargs}")
    
    # Call with **kwargs unpacking
    await modify_kwargs(**original_data)
    
    logger.info(f"Original data after function call: {original_data}")
    
    print("As expected, original_data is unchanged because **kwargs creates a copy")
    
    # Now test the correct way
    async def modify_kwargs_correct(data_dict):
        logger.info(f"Inside function - data_dict before: {data_dict}")
        # Modify the actual dictionary
        data_dict["messages"] = [{"role": "user"}]  # Remove created_at
        logger.info(f"Inside function - data_dict after: {data_dict}")
    
    original_data2 = {"messages": [{"role": "user", "created_at": 12345}]}
    logger.info(f"Original data2: {original_data2}")
    
    await modify_kwargs_correct(original_data2)
    
    logger.info(f"Original data2 after function call: {original_data2}")
    print("This time the original data was modified")

if __name__ == "__main__":
    asyncio.run(test_kwargs_issue())