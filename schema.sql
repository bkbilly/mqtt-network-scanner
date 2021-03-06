CREATE TABLE IF NOT EXISTS devices (
  mac TEXT PRIMARY KEY,
  ip TEXT NOT NULL,
  name TEXT DEFAULT '',
  vendor TEXT DEFAULT '',
  hostname TEXT DEFAULT '',
  brand TEXT DEFAULT '',
  model TEXT DEFAULT '',
  active BOOLEAN DEFAULT true,
  notify_away BOOLEAN DEFAULT false,
  is_recognized BOOLEAN DEFAULT false,
  icon TEXT DEFAULT 'radar',
  devicetype TEXT DEFAULT '',
  last_changed DATETIME DEFAULT CURRENT_TIMESTAMP,
  created DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS events (
  mac TEXT PRIMARY KEY,
  active BOOLEAN NOT NULL,
  updated DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (mac)
    REFERENCES devices (mac) 
      ON DELETE CASCADE 
      ON UPDATE NO ACTION
);
