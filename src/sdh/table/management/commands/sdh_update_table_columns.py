from django.core.management.base import BaseCommand
from sdh.table.models import TableViewProfile


class Command(BaseCommand):
    help = (
        "Update table columns to match renames in source code."
        "Ex. ./manage.py sdh_update_table_columns --name workorder_profile "
        "--column old_name:new_name --column old_name2:new_name2"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--name', '-n', action='store', dest='name',
            help='Name of table.'
        )
        parser.add_argument(
            '--column', '-c', action='append', dest='columns', help='Columns mapping.'
        )

    def handle(self, *args, **options):
        tableview_name = options.get('name')
        columns = options.get('columns')
        if not tableview_name:
            self.stdout.write(self.style.ERROR('Parameter --name is required.'))
            return
        if not columns:
            self.stdout.write(self.style.ERROR('Parameter --column is required.'))

        items = TableViewProfile.objects.filter(tableview_name=tableview_name)
        for item in items:
            state = item.state
            if state and 'visible' not in state:
                continue
            changed = False
            for column in columns:
                old_column, new_column = column.split(':')
                if old_column in state['visible']:
                    state['visible'].remove(old_column)
                    state['visible'].append(new_column)
                    changed = True
            if changed:
                self.stdout.write(f'Update table "{item.tableview_name}" named "{item.label}" for user "{item.user.label}". (id: {item.id})')
            item.dump = item.dump_state(state)
            item.save()
