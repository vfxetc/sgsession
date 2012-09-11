from subprocess import call
import datetime
import os
import atexit
import itertools

import shotgun_api3_registry
import sgmock

sg = None
project = {}
sequences = []
shots = []
tasks = []

timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
root = os.path.join(os.path.dirname(__file__), 'root_' + timestamp)

def mini_uuid():
    return os.urandom(4).encode('hex')


def setup_sg():
    global sg
    if not sg:
        sg = sgmock.Shotgun()
        fix = sgmock.Fixture(sg)
        fix.default_steps()
        # sg = shotgun_api3_registry.connect(name='sgfs.tests', server='testing')


def setup_project():
    setup_sg()
    if not project:
        if not os.path.exists(root):
            os.makedirs(root)
        project.update(type="Project", id=sg.create('Project', dict(
            name='test_project_%s' % (timestamp),
            sg_code='test_project_%s' % (timestamp), # Only on test server.
            sg_description='For unit testing.',
        ))['id'])


def setup_sequences():
    
    if sequences:
        return
    
    setup_project()
    
    batch = []
    
    for seq_code in ('AA', 'BB'):
        batch.append(dict(
            request_type='create',
            entity_type='Sequence',
            data=dict(
                code=seq_code,
                project=project,
            )
        ))
    for x in sg.batch(batch):
        sequences.append(dict(type="Sequence", id=x['id']))
    
    batch = []
    for seq_code, seq in zip(('AA', 'BB'), sequences):
        for shot_i in range(1, 3):
            batch.append(dict(
                request_type='create',
                entity_type='Shot',
                data=dict(
                    description='Test Shot %s-%s' % (seq_code, shot_i),
                    code='%s_%03d' % (seq_code, shot_i),
                    sg_sequence=seq,
                    project=project,
                )
            ))
    for x in sg.batch(batch):
        shots.append(dict(type="Shot", id=x['id']))
    

def setup_tasks():
    
    if tasks:
        return
    
    setup_sequences()
    
    steps = sg.find('Step', [])
    
    batch = []
    for shot in shots:
        for i in range(3):
            batch.append(dict(
                request_type='create',
                entity_type='Task',
                data=dict(
                    entity=shot,
                    project=project,
                    content=mini_uuid(),
                    step=steps[i],
                )
            ))
    for x in sg.batch(batch):
        tasks.append(dict(type="Task", id=x['id']))
            
            

do_tear_down = True

@atexit.register
def tear_down():
    
    if not do_tear_down:
        return
        
    if os.path.exists(root):
        call(['rm', '-rf', root])
    
    # Delete all entities.
    if not sg:
        return
    sg.batch([
        {'request_type': 'delete', 'entity_type': x['type'], 'entity_id': x['id']}
        for x in itertools.chain(tasks, shots, sequences, [project])
        if x
    ])

