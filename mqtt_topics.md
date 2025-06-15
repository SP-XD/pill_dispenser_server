
| Direction   | Topic                              | Purpose                                                   |
| ----------- | ---------------------------------- | --------------------------------------------------------- |
| Server → Pi | `pill/{device_id}/command`         | Dispense, refill, or change hard mode                     |
| Server → Pi | `pill/{device_id}/schedule/set`    | Send new schedule to the device                           |
| Server → Pi | `pill/{device_id}/settings/update` | Push hard mode / threshold configs                        |
| Pi → Server | `pill/{device_id}/status`          | Send back action statuses (dispense taken/not, etc.)      |
| Pi → Server | `pill/{device_id}/schedule/status` | Schedule confirmations or triggered execution logs        |
| Pi → Server | `pill/{device_id}/settings/status` | Settings confirmation messages                            |
| Pi → Server | `pill/{device_id}/alerts`          | Critical device-level alerts (low pill, missed dose etc.) |
