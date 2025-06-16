def transform_schedule_for_mqtt(schedules):
    """Transform database schedule format to MQTT format"""
    time_groups = {}
    
    for schedule in schedules:
        time = schedule['time']
        if time not in time_groups:
            time_groups[time] = {
                'time': time,
                'dispenser_modules': [],
                'days': schedule.get('days', ['daily']),
                'until_date': schedule.get('until_date')
            }
        time_groups[time]['dispenser_modules'].append(schedule['module'])
    
    return list(time_groups.values())