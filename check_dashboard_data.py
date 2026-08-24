import asyncio
from sqlalchemy import text
from shared.database import get_db

async def check_dashboard_data():
    db_gen = get_db()
    db = await db_gen.__anext__()
    try:
        # Check observations
        result = await db.execute(text('SELECT COUNT(*) FROM observations'))
        print(f'Observations count: {result.scalar()}')
        
        # Check KPIs
        result = await db.execute(text('SELECT COUNT(*) FROM kpis'))
        print(f'KPIs count: {result.scalar()}')
        
        # Check tasks
        result = await db.execute(text('SELECT COUNT(*) FROM tasks'))
        print(f'Tasks count: {result.scalar()}')
        
        # Check compliance_observations
        result = await db.execute(text('SELECT COUNT(*) FROM compliance_observations'))
        print(f'Compliance observations count: {result.scalar()}')
        
        # Check discrepancies
        result = await db.execute(text('SELECT COUNT(*) FROM discrepancies'))
        print(f'Discrepancies count: {result.scalar()}')
        
        # Check observations with auto_result
        result = await db.execute(text('SELECT COUNT(*) FROM observations WHERE auto_result IS NOT NULL'))
        print(f'Observations with auto_result: {result.scalar()}')
        
        # Check recent observations
        result = await db.execute(text('SELECT COUNT(*) FROM observations WHERE submitted_at >= NOW() - INTERVAL \'30 days\''))
        print(f'Recent observations (30 days): {result.scalar()}')
        
        # Check schools
        result = await db.execute(text('SELECT COUNT(*) FROM schools'))
        print(f'Schools count: {result.scalar()}')
        
        # Check users
        result = await db.execute(text('SELECT COUNT(*) FROM users'))
        print(f'Users count: {result.scalar()}')
        
        # Check departments
        result = await db.execute(text('SELECT COUNT(*) FROM departments'))
        print(f'Departments count: {result.scalar()}')
        
        # Check departments by school
        result = await db.execute(text('SELECT school_id, COUNT(*) FROM departments GROUP BY school_id'))
        dept_by_school = result.fetchall()
        print(f'Departments by school: {dept_by_school}')
        
        # List all departments
        result = await db.execute(text('SELECT d.name, d.code, s.name as school_name FROM departments d JOIN schools s ON d.school_id = s.id'))
        departments = result.fetchall()
        print(f'All departments:')
        for dept in departments:
            print(f'  - {dept[0]} ({dept[1]}) in {dept[2]}')
        
    finally:
        try:
            await db_gen.__anext__()
        except StopAsyncIteration:
            pass

if __name__ == "__main__":
    asyncio.run(check_dashboard_data())