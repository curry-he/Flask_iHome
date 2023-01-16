from flask_script import Manager
from flask_migrate import Migrate, MigrateCommand
from iHome import create_app, db

# 创建app
app = create_app("develop")
manage = Manager(app)
Migrate(app, db)
manage.add_command('db', MigrateCommand)

if __name__ == '__main__':
    manage.run()
