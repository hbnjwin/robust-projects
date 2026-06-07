import pandas as pd
from sqlalchemy import create_engine

engine = create_engine("postgresql://localhost/analytics")

def calculate_retention(cohort_date: str, period: int = 7) -> pd.DataFrame:
    query = """
    WITH cohort AS (
        SELECT user_id, MIN(DATE(created_at)) as first_day
        FROM events WHERE DATE(created_at) = %s
        GROUP BY user_id
    ),
    activity AS (
        SELECT c.user_id, DATE(e.created_at) as active_date,
               DATEDIFF(DATE(e.created_at), c.first_day) as day_n
        FROM cohort c
        JOIN events e ON c.user_id = e.user_id
    )
    SELECT day_n, COUNT(DISTINCT user_id) as retained_users,
           COUNT(DISTINCT user_id) * 1.0 / (SELECT COUNT(*) FROM cohort) as retention_rate
    FROM activity WHERE day_n <= %s
    GROUP BY day_n ORDER BY day_n
    """
    # BUG: retention calculation may be incorrect - needs review
    return pd.read_sql(query, engine, params=[cohort_date, period])
