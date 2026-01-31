"""
Database module for PostgreSQL read-only operations.
Handles connection management and skill fetching.
"""

import os
from typing import List, Tuple
from contextlib import contextmanager

import psycopg2
from psycopg2.extras import RealDictCursor


def get_db_config() -> dict:
    """
    Retrieve database configuration from environment variables.
    Raises ValueError if required variables are missing.
    """
    required_vars = ["DB_NAME", "DB_USER", "DB_PASSWORD", "DB_HOST", "DB_PORT"]
    config = {}
    
    for var in required_vars:
        value = os.environ.get(var)
        if value is None:
            raise ValueError(f"Missing required environment variable: {var}")
        config[var] = value
    
    return {
        "dbname": config["DB_NAME"],
        "user": config["DB_USER"],
        "password": config["DB_PASSWORD"],
        "host": config["DB_HOST"],
        "port": int(config["DB_PORT"]),
    }


@contextmanager
def get_connection():
    """
    Context manager for database connections.
    Ensures connections are properly closed after use.
    """
    conn = None
    try:
        conn = psycopg2.connect(**get_db_config())
        yield conn
    except psycopg2.Error as e:
        raise ConnectionError(f"Database connection failed: {e}")
    finally:
        if conn is not None:
            conn.close()


def fetch_active_skills() -> List[Tuple[int, str]]:
    """
    Fetch all active skills from database.
    
    Returns:
        List of tuples containing (skill_id, skill_name)
        Only returns skills where curatal_skill = 1 (active)
    
    Raises:
        ConnectionError: If database connection fails
        RuntimeError: If query execution fails
    """
    query = """
        SELECT skill_id, skill_name
        FROM skill_taxonamy
        WHERE curatal_skill = 1
        ORDER BY skill_id
    """
    
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query)
                rows = cursor.fetchall()
                
                # Filter out any rows with None or empty skill_name
                valid_skills = [
                    (row[0], row[1])
                    for row in rows
                    if row[0] is not None and row[1] is not None and row[1].strip()
                ]
                
                return valid_skills
                
    except psycopg2.Error as e:
        raise RuntimeError(f"Failed to fetch skills: {e}")


def test_connection() -> bool:
    """
    Test database connectivity.
    
    Returns:
        True if connection is successful
    
    Raises:
        ConnectionError: If connection fails
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1")
                return True
    except Exception as e:
        raise ConnectionError(f"Database connection test failed: {e}")
