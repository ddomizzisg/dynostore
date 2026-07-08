const express = require('express');
const Docker = require('dockerode');
const fs = require('fs');
const yaml = require('yaml');
const path = require('path');
const cors = require('cors');
const { PassThrough } = require('stream');

const app = express();
const docker = new Docker({ socketPath: '/var/run/docker.sock' });
const PORT = process.env.PORT || 8080;

app.use(cors());
app.use(express.static('public'));

// Helper to run exec inside a container
async function execInContainer(container, cmdArray) {
    const exec = await container.exec({
        Cmd: cmdArray,
        AttachStdout: true,
        AttachStderr: true
    });
    
    return new Promise((resolve, reject) => {
        exec.start((err, stream) => {
            if (err) return reject(err);
            let output = '';
            stream.on('data', chunk => output += chunk.toString());
            stream.on('end', () => resolve(output));
        });
    });
}

function getTargetServices() {
    try {
        const file = fs.readFileSync(path.join(__dirname, '..', 'docker-compose.dev.yml'), 'utf8');
        const parsed = yaml.parse(file);
        if (parsed && parsed.services) {
            return Object.keys(parsed.services);
        }
        return [];
    } catch (e) {
        console.error('Error parsing docker-compose.dev.yml', e);
        return [];
    }
}

async function getMonitoredContainers() {
    const targetServices = getTargetServices();
    const containers = await docker.listContainers({ all: true });
    return containers.filter(c => {
        const labels = c.Labels || {};
        const serviceName = labels['com.docker.compose.service'];
        return targetServices.includes(serviceName) || targetServices.some(ts => c.Names.some(n => n.includes(ts)));
    });
}

app.get('/api/containers', async (req, res) => {
    try {
        const monitored = await getMonitoredContainers();
        const statusList = monitored.map(c => ({
            id: c.Id,
            names: c.Names,
            image: c.Image,
            state: c.State,
            status: c.Status,
            service: c.Labels['com.docker.compose.service'] || 'unknown'
        }));
        res.json(statusList);
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

app.get('/api/stats', async (req, res) => {
    try {
        const monitored = await getMonitoredContainers();
        const statsPromises = monitored.filter(c => c.State === 'running').map(async c => {
            const container = docker.getContainer(c.Id);
            const stats = await container.stats({ stream: false });
            
            // Calculate CPU
            const cpuDelta = stats.cpu_stats.cpu_usage.total_usage - stats.precpu_stats.cpu_usage.total_usage;
            const systemDelta = stats.cpu_stats.system_cpu_usage - stats.precpu_stats.system_cpu_usage;
            const cpus = stats.cpu_stats.online_cpus || stats.cpu_stats.cpu_usage.percpu_usage?.length || 1;
            let cpuPercent = 0.0;
            if (systemDelta > 0.0 && cpuDelta > 0.0) {
                cpuPercent = (cpuDelta / systemDelta) * cpus * 100.0;
            }

            // Calculate Memory
            const memUsage = stats.memory_stats.usage || 0;
            const memLimit = stats.memory_stats.limit || 1;
            const memPercent = (memUsage / memLimit) * 100.0;

            const formatBytes = (bytes) => {
                if (bytes === 0) return '0 B';
                const k = 1024, sizes = ['B', 'KB', 'MB', 'GB', 'TB'], i = Math.floor(Math.log(bytes) / Math.log(k));
                return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
            };

            return {
                id: c.Id,
                cpu: cpuPercent.toFixed(2) + '%',
                memory: `${formatBytes(memUsage)} / ${formatBytes(memLimit)} (${memPercent.toFixed(2)}%)`
            };
        });

        const statsList = await Promise.all(statsPromises);
        res.json(statsList);
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

app.get('/api/storage', async (req, res) => {
    try {
        const containers = await getMonitoredContainers();
        const dataContainers = containers.filter(c => c.Names.some(n => n.includes('datacontainer')));
        
        const storagePromises = dataContainers.map(async c => {
            if (c.State !== 'running') return { id: c.Id, storage: 'Offline' };
            const container = docker.getContainer(c.Id);
            try {
                const output = await execInContainer(container, ['sh', '-c', 'du -sb /data/objects 2>/dev/null || echo "0"']);
                const bytes = parseInt(output.split('\t')[0].trim()) || 0;
                
                const formatBytes = (bytes) => {
                    if (isNaN(bytes) || bytes === 0) return '0 B';
                    const k = 1024, sizes = ['B', 'KB', 'MB', 'GB', 'TB'], i = Math.floor(Math.log(bytes) / Math.log(k));
                    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
                };

                return {
                    id: c.Id,
                    storage: formatBytes(bytes)
                };
            } catch (err) {
                return { id: c.Id, storage: 'N/A' };
            }
        });

        const storageList = await Promise.all(storagePromises);
        res.json(storageList);
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

app.get('/api/logs/:id', async (req, res) => {
    const { id } = req.params;
    res.setHeader('Content-Type', 'text/event-stream');
    res.setHeader('Cache-Control', 'no-cache');
    res.setHeader('Connection', 'keep-alive');
    res.flushHeaders();

    try {
        const container = docker.getContainer(id);
        const logStream = await container.logs({ follow: true, stdout: true, stderr: true, tail: 100 });
        const passThrough = new PassThrough();
        container.modem.demuxStream(logStream, passThrough, passThrough);
        
        passThrough.on('data', chunk => {
            const lines = chunk.toString('utf8').split('\n');
            lines.forEach(line => {
                if (line.trim()) {
                    res.write(`data: ${JSON.stringify(line.trim())}\n\n`);
                }
            });
        });

        logStream.on('end', () => res.write('event: end\ndata: stream closed\n\n'));
        req.on('close', () => res.end());
    } catch (error) {
        res.write(`event: error\ndata: ${JSON.stringify(error.message)}\n\n`);
        res.end();
    }
});

// Cleanup API: Data
app.post('/api/cleanup/data', async (req, res) => {
    try {
        const containers = await getMonitoredContainers();
        const dataContainers = containers.filter(c => c.Names.some(n => n.includes('datacontainer')));
        
        for (const c of dataContainers) {
            const container = docker.getContainer(c.Id);
            await execInContainer(container, ['sh', '-c', 'rm -rf /data/objects/*']);
        }
        res.json({ success: true, message: 'Data containers cleaned' });
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
});

// Cleanup API: Logs
app.post('/api/cleanup/logs', async (req, res) => {
    try {
        const containers = await getMonitoredContainers();
        for (const c of containers) {
            const container = docker.getContainer(c.Id);
            const service = c.Labels['com.docker.compose.service'];
            
            if (service === 'auth') {
                await execInContainer(container, ['sh', '-c', 'rm -rf /var/www/html/log/*']);
            } else if (service === 'pub_sub') {
                await execInContainer(container, ['sh', '-c', 'rm -rf /var/www/html/log/*']);
            } else if (service === 'apigateway' || service?.startsWith('datacontainer')) {
                await execInContainer(container, ['sh', '-c', 'rm -rf /app/logs/*']);
            }
        }
        res.json({ success: true, message: 'Logs cleaned' });
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
});

// Cleanup API: Metadata
app.post('/api/cleanup/metadata', async (req, res) => {
    try {
        const containers = await getMonitoredContainers();
        
        for (const c of containers) {
            const container = docker.getContainer(c.Id);
            const service = c.Labels['com.docker.compose.service'];
            
            if (service === 'db_auth') {
                // Delete from logs, preserve users etc
                await execInContainer(container, ['sh', '-c', 'psql -U muyalmanager -d auth -c "DELETE FROM logs;"']);
            } else if (service === 'db_pub_sub') {
                // Delete from files tables, preserve catalogs etc
                await execInContainer(container, ['sh', '-c', 'psql -U muyalmanager -d pub_sub -c "DELETE FROM groups_files; DELETE FROM shared_files; DELETE FROM catalogs_files; DELETE FROM users_files;"']);
            } else if (service === 'db_metadata') {
                // Delete files and cascade chunks, preserve servers
                await execInContainer(container, ['sh', '-c', 'psql -U metadata -d metadata-api -c "DELETE FROM chunks; DELETE FROM abekeys; DELETE FROM files_in_servers; DELETE FROM files;"']);
            }
        }
        
        res.json({ success: true, message: 'Metadata cleaned' });
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
});

app.listen(PORT, () => {
    console.log(`Monitor service listening on port ${PORT}`);
});
