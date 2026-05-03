// API Base URL
const API_BASE = '/api';
const CSRF_TOKEN = document.querySelector('meta[name="csrf-token"]')?.content || '';

function encodeApiPathSegment(value) {
    return encodeURIComponent(String(value ?? ''));
}

function buildApiUrl(pathSegments = [], queryParams = null) {
    const encodedPath = pathSegments.length > 0
        ? `/${pathSegments.map(encodeApiPathSegment).join('/')}`
        : '';
    const searchParams = new URLSearchParams();

    if (queryParams) {
        Object.entries(queryParams).forEach(([key, value]) => {
            if (value === undefined || value === null || value === '') {
                return;
            }
            searchParams.append(key, String(value));
        });
    }

    const queryString = searchParams.toString();
    return `${API_BASE}${encodedPath}${queryString ? `?${queryString}` : ''}`;
}

function withCsrfHeaders(headers = {}) {
    return {
        ...headers,
        'X-CSRF-Token': CSRF_TOKEN
    };
}

function escapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function escapeInlineHandlerArg(value) {
    return escapeHtml(String(value ?? ''))
        .replace(/\\/g, '\\\\')
        .replace(/&#39;/g, "\\'")
        .replace(/\r/g, '\\r')
        .replace(/\n/g, '\\n')
        .replace(/\u2028/g, '\\u2028')
        .replace(/\u2029/g, '\\u2029');
}

function safeDomId(value) {
    return encodeURIComponent(String(value ?? ''));
}

function sanitizeClassToken(value, fallback = 'unknown') {
    const token = String(value ?? '').trim();
    return /^[a-zA-Z0-9_-]+$/.test(token) ? token : fallback;
}

// Global state
let devicesData = {};
let schedulesData = {};
let autoRestartData = {};

// Load devices and display them
async function loadDevices() {
    try {
        const response = await fetch(`${API_BASE}/devices`);
        const data = await response.json();
        devicesData = data.devices || {};
        
        const container = document.getElementById('devices-container');
        container.innerHTML = '';
        
        // Update device count
        document.getElementById('device-count').textContent = `${Object.keys(devicesData).length} Devices`;
        
        // Update device filter dropdowns
        updateDeviceSelects();
        
        for (const [name, device] of Object.entries(devicesData)) {
            // Create device card
            const card = createDeviceCard(name, device);
            container.appendChild(card);
        }
        
        // Load status for all devices
        await refreshAll();
        // Load schedules and auto restart
        await loadSchedules();
        await loadAutoRestart();
    } catch (error) {
        showToast('Error loading devices: ' + error.message, 'error');
    }
}

// Update device selects in modals
function updateDeviceSelects() {
    const selects = ['log-device-filter', 'schedule-device-select', 'auto-restart-device-select'];
    selects.forEach(selectId => {
        const select = document.getElementById(selectId);
        if (select) {
            const currentValue = select.value;
            select.innerHTML = selectId === 'log-device-filter' 
                ? '<option value="">All Devices</option>'
                : '<option value="">Select Device</option>';
            
            for (const name of Object.keys(devicesData)) {
                const option = document.createElement('option');
                option.value = name;
                option.textContent = name;
                select.appendChild(option);
            }
            
            if (currentValue && devicesData[currentValue]) {
                select.value = currentValue;
            }
        }
    });
}

// Create device card element (more compact)
function createDeviceCard(name, device) {
    const col = document.createElement('div');
    col.className = 'col-md-6 col-lg-4 col-xl-3';
    const escapedName = escapeHtml(name);
    const escapedType = escapeHtml(device?.type);
    const handlerName = escapeInlineHandlerArg(name);
    const cardId = `device-${safeDomId(name)}`;
    const healthId = `health-${safeDomId(name)}`;
    const statusId = `status-${safeDomId(name)}`;
    
    col.innerHTML = `
        <div class="card device-card device-card-compact" id="${cardId}">
            <div class="card-header">
                <span><i class="bi bi-device-hdd"></i> ${escapedName}</span>
                <span class="badge bg-light text-dark">${escapedType}</span>
            </div>
            <div class="card-body">
                <div class="d-flex justify-content-between align-items-center mb-2">
                    <small class="text-muted">Health:</small>
                    <span id="${healthId}" class="health-online">
                        <i class="bi bi-circle-fill"></i> <small>Checking...</small>
                    </span>
                </div>
                <div class="d-flex justify-content-between align-items-center mb-3">
                    <small class="text-muted">EarnApp:</small>
                    <span id="${statusId}" class="status-badge status-unknown">
                        <small>Checking...</small>
                    </span>
                </div>
                <div class="btn-group w-100 mb-2" role="group">
                    <button class="btn btn-success btn-sm btn-action" onclick="startDevice('${handlerName}')" title="Start">
                        <i class="bi bi-play"></i>
                    </button>
                    <button class="btn btn-danger btn-sm btn-action" onclick="stopDevice('${handlerName}')" title="Stop">
                        <i class="bi bi-stop"></i>
                    </button>
                    <button class="btn btn-warning btn-sm btn-action" onclick="restartDevice('${handlerName}')" title="Restart">
                        <i class="bi bi-arrow-repeat"></i>
                    </button>
                </div>
                <div class="d-grid gap-1">
                    <button class="btn btn-info btn-sm" onclick="showDeviceId('${handlerName}')" title="Show Device ID">
                        <i class="bi bi-info-circle"></i> ID
                    </button>
                    <button class="btn btn-outline-danger btn-sm" onclick="deleteDevice('${handlerName}')" title="Delete Device">
                        <i class="bi bi-trash"></i> Delete
                    </button>
                </div>
            </div>
        </div>
    `;
    
    return col;
}

// Refresh all device statuses and update stats
async function refreshAll() {
    try {
        const response = await fetch(`${API_BASE}/devices/all/status`);
        const data = await response.json();
        const devices = data.devices || [];
        
        let running = 0, stopped = 0, online = 0;
        
        devices.forEach(device => {
            updateDeviceStatus(device.name, device);
            
            if (device.earnapp_status === 'Running') running++;
            if (device.earnapp_status === 'Stopped') stopped++;
            if (device.health === 'online') online++;
        });
        
        // Update stats
        document.getElementById('stats-running').textContent = running;
        document.getElementById('stats-stopped').textContent = stopped;
        document.getElementById('stats-online').textContent = online;
        
        showToast('Status refreshed', 'success');
    } catch (error) {
        showToast('Error refreshing status: ' + error.message, 'error');
    }
}

// Update device status display
function updateDeviceStatus(name, status) {
    const healthEl = document.getElementById(`health-${safeDomId(name)}`);
    const statusEl = document.getElementById(`status-${safeDomId(name)}`);
    
    if (healthEl) {
        if (status.health === 'online') {
            healthEl.className = 'health-online';
            healthEl.innerHTML = '<i class="bi bi-circle-fill"></i> <small>Online</small>';
        } else {
            healthEl.className = 'health-offline';
            healthEl.innerHTML = '<i class="bi bi-circle-fill"></i> <small>Offline</small>';
        }
    }
    
    if (statusEl) {
        statusEl.textContent = status.earnapp_status;
        statusEl.className = 'status-badge';
        
        if (status.earnapp_status === 'Running') {
            statusEl.classList.add('status-running');
        } else if (status.earnapp_status === 'Stopped') {
            statusEl.classList.add('status-stopped');
        } else {
            statusEl.classList.add('status-unknown');
        }
    }
}

// Start device
async function startDevice(name) {
    const card = document.getElementById(`device-${safeDomId(name)}`);
    if (card) card.classList.add('loading');
    
    try {
        const response = await fetch(buildApiUrl(['devices', name, 'start']), {
            method: 'POST',
            headers: withCsrfHeaders()
        });
        const data = await response.json();
        
        if (data.success) {
            showToast(`Device ${name} started`, 'success');
            await refreshAll();
            await loadActivityLogs();
        } else {
            showToast(`Error: ${data.message || 'Unknown error'}`, 'error');
        }
    } catch (error) {
        showToast('Error: ' + error.message, 'error');
    } finally {
        if (card) card.classList.remove('loading');
    }
}

// Stop device
async function stopDevice(name) {
    if (!confirm(`Stop ${name}?`)) return;
    
    const card = document.getElementById(`device-${safeDomId(name)}`);
    if (card) card.classList.add('loading');
    
    try {
        const response = await fetch(buildApiUrl(['devices', name, 'stop']), {
            method: 'POST',
            headers: withCsrfHeaders()
        });
        const data = await response.json();
        
        if (data.success) {
            showToast(`Device ${name} stopped`, 'success');
            await refreshAll();
            await loadActivityLogs();
        } else {
            showToast(`Error: ${data.message || 'Unknown error'}`, 'error');
        }
    } catch (error) {
        showToast('Error: ' + error.message, 'error');
    } finally {
        if (card) card.classList.remove('loading');
    }
}

// Restart device
async function restartDevice(name) {
    const card = document.getElementById(`device-${safeDomId(name)}`);
    if (card) card.classList.add('loading');
    
    try {
        const response = await fetch(buildApiUrl(['devices', name, 'restart']), {
            method: 'POST',
            headers: withCsrfHeaders()
        });
        const data = await response.json();
        
        if (data.success) {
            showToast(`Device ${name} restarted`, 'success');
            await refreshAll();
            await loadActivityLogs();
        } else {
            showToast(`Error: ${data.message || 'Unknown error'}`, 'error');
        }
    } catch (error) {
        showToast('Error: ' + error.message, 'error');
    } finally {
        if (card) card.classList.remove('loading');
    }
}

// Quick restart all
async function quickRestartAll() {
    if (!confirm('Quick restart all devices? (Stop → Wait 5s → Start)')) return;
    
    try {
        const response = await fetch(buildApiUrl(['devices', 'all', 'restart']), {
            method: 'POST',
            headers: withCsrfHeaders()
        });
        const data = await response.json();
        
        if (data.success) {
            showToast('All devices restarted', 'success');
            await refreshAll();
            await loadActivityLogs();
        } else {
            showToast(`Error: ${data.message || 'Unknown error'}`, 'error');
        }
    } catch (error) {
        showToast('Error: ' + error.message, 'error');
    }
}

// Health check all
async function healthCheckAll() {
    try {
        const response = await fetch(`${API_BASE}/devices/all/health-check`, {
            method: 'POST',
            headers: withCsrfHeaders()
        });
        const data = await response.json();
        
        if (data.success) {
            showToast('Health check completed', 'success');
            await refreshAll();
        }
    } catch (error) {
        showToast('Error: ' + error.message, 'error');
    }
}

// Start all devices
async function startAllDevices() {
    if (!confirm('Start all devices?')) return;
    
    try {
        const response = await fetch(`${API_BASE}/devices/all/start`, {
            method: 'POST',
            headers: withCsrfHeaders()
        });
        const data = await response.json();
        
        if (data.success) {
            showToast('All devices started', 'success');
            await refreshAll();
            await loadActivityLogs();
        }
    } catch (error) {
        showToast('Error: ' + error.message, 'error');
    }
}

// Stop all devices
async function stopAllDevices() {
    if (!confirm('Stop all devices?')) return;
    
    try {
        const response = await fetch(`${API_BASE}/devices/all/stop`, {
            method: 'POST',
            headers: withCsrfHeaders()
        });
        const data = await response.json();
        
        if (data.success) {
            showToast('All devices stopped', 'success');
            await refreshAll();
            await loadActivityLogs();
        }
    } catch (error) {
        showToast('Error: ' + error.message, 'error');
    }
}

// Show device ID
async function showDeviceId(name) {
    try {
        const response = await fetch(buildApiUrl(['devices', name, 'id']));
        const data = await response.json();
        
        if (data.success) {
            alert(`Device ID: ${name}\n\n${data.result}`);
        } else {
            showToast('Error getting device ID', 'error');
        }
    } catch (error) {
        showToast('Error: ' + error.message, 'error');
    }
}

// Delete device
async function deleteDevice(name) {
    if (!confirm(`Delete device "${name}"?`)) return;
    
    try {
        const response = await fetch(buildApiUrl(['devices', name]), {
            method: 'DELETE',
            headers: withCsrfHeaders()
        });
        const data = await response.json();
        
        if (data.success) {
            showToast(`Device ${name} deleted`, 'success');
            await loadDevices();
        } else {
            showToast(`Error: ${data.message || 'Unknown error'}`, 'error');
        }
    } catch (error) {
        showToast('Error: ' + error.message, 'error');
    }
}

// Show add device modal
function showAddDeviceModal() {
    const modal = new bootstrap.Modal(document.getElementById('addDeviceModal'));
    modal.show();
}

// Toggle device type fields
function toggleDeviceTypeFields() {
    const type = document.getElementById('device-type-select').value;
    document.getElementById('ssh-fields').style.display = type === 'ssh' ? 'block' : 'none';
    document.getElementById('adb-fields').style.display = type === 'adb' ? 'block' : 'none';
    document.getElementById('local-fields').style.display = type === 'local' ? 'block' : 'none';
}

// Submit add device form
async function submitAddDevice() {
    const form = document.getElementById('add-device-form');
    const type = form.querySelector('[name="type"]').value;
    const data = {
        name: form.querySelector('[name="name"]').value,
        type: type
    };

    if (type === 'ssh') {
        const sshFields = document.getElementById('ssh-fields');
        data.host = sshFields.querySelector('[name="host"]').value;
        data.port = parseInt(sshFields.querySelector('[name="port"]').value, 10);
        data.user = sshFields.querySelector('[name="user"]').value;
        data.password = sshFields.querySelector('[name="password"]').value;
    } else if (type === 'adb') {
        const adbFields = document.getElementById('adb-fields');
        data.host = adbFields.querySelector('[name="host"]').value;
        data.port = parseInt(adbFields.querySelector('[name="port"]').value, 10);
    } else if (type === 'local') {
        const localFields = document.getElementById('local-fields');
        data.path = localFields.querySelector('[name="path"]').value;
    }
    
    try {
        const response = await fetch(`${API_BASE}/devices`, {
            method: 'POST',
            headers: withCsrfHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify(data)
        });
        
        const result = await response.json();
        
        if (result.success) {
            showToast(result.message, 'success');
            bootstrap.Modal.getInstance(document.getElementById('addDeviceModal')).hide();
            form.reset();
            await loadDevices();
        } else {
            showToast(`Error: ${result.message || 'Unknown error'}`, 'error');
        }
    } catch (error) {
        showToast('Error: ' + error.message, 'error');
    }
}

// Load activity logs with filters
async function loadActivityLogs() {
    try {
        const deviceFilter = document.getElementById('log-device-filter').value;
        const typeFilter = document.getElementById('log-type-filter').value;
        const dateFilter = document.getElementById('log-date-filter').value;
        
        const response = await fetch(buildApiUrl(['activity-logs'], {
            limit: 100,
            device: deviceFilter
        }));
        const data = await response.json();
        let logs = data.logs || [];
        
        // Filter by type
        if (typeFilter) {
            logs = logs.filter(log => log.type === typeFilter);
        }
        
        // Filter by date
        if (dateFilter) {
            const filterDate = new Date(dateFilter);
            logs = logs.filter(log => {
                const logDate = new Date(log.timestamp * 1000);
                return logDate.toDateString() === filterDate.toDateString();
            });
        }
        
        const container = document.getElementById('activity-logs');
        container.innerHTML = '';
        
        if (logs.length === 0) {
            container.innerHTML = '<div class="empty-state"><i class="bi bi-inbox"></i><p>No activity logs</p></div>';
            return;
        }
        
        logs.reverse().forEach(log => {
            const entry = document.createElement('div');
            entry.className = 'log-entry';
            
            const actionClass = log.action === 'start' ? 'start' : 
                               log.action === 'stop' ? 'stop' : 'restart';
            const typeClass = sanitizeClassToken(log.type, 'manual');
            const formattedTime = escapeHtml(log.formatted_time || 'Unknown');
            const actionText = escapeHtml(String(log.action || 'unknown').toUpperCase());
            const deviceName = escapeHtml(log.device || 'Unknown device');
            const typeText = escapeHtml(log.type || 'manual');
            const resultText = log.result
                ? `${escapeHtml(log.result.substring(0, 150))}${log.result.length > 150 ? '...' : ''}`
                : '';
            
            entry.innerHTML = `
                <div class="d-flex justify-content-between align-items-start">
                    <div class="flex-grow-1">
                        <span class="log-time">${formattedTime}</span>
                        <span class="log-action ${actionClass}">${actionText}</span>
                        <strong>${deviceName}</strong>
                        <span class="log-type ${typeClass}">${typeText}</span>
                    </div>
                </div>
                ${log.result ? `<div class="text-muted small mt-1">${resultText}</div>` : ''}
            `;
            
            container.appendChild(entry);
        });
    } catch (error) {
        showToast('Error loading logs: ' + error.message, 'error');
    }
}

// Load schedules
async function loadSchedules() {
    try {
        const response = await fetch(`${API_BASE}/schedules`);
        const data = await response.json();
        schedulesData = data.schedules || {};
        
        const container = document.getElementById('schedules-list');
        container.innerHTML = '';
        
        // Update stats
        const activeSchedules = Object.values(schedulesData).filter(s => s.enabled !== false).length;
        document.getElementById('stats-schedules').textContent = activeSchedules;
        
        if (Object.keys(schedulesData).length === 0) {
            container.innerHTML = '<div class="empty-state"><i class="bi bi-calendar-x"></i><p>No schedules configured</p></div>';
            return;
        }
        
        const daysNames = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
        
        for (const [taskId, schedule] of Object.entries(schedulesData)) {
            const item = document.createElement('div');
            item.className = 'schedule-item';
            
            const days = schedule.days || [];
            const daysStr = days.map(d => daysNames[d]).join(', ') || 'None';
            const statusIcon = schedule.enabled !== false ? '✅' : '❌';
            const escapedTaskId = escapeInlineHandlerArg(taskId);
            const deviceName = escapeHtml(schedule.device || 'Unknown device');
            const scheduleTime = escapeHtml(schedule.time || 'Unknown time');
            const actionText = escapeHtml(String(schedule.action || 'unknown').toUpperCase());
            const daysText = escapeHtml(daysStr);
            
            item.innerHTML = `
                <div class="d-flex justify-content-between align-items-start">
                    <div class="flex-grow-1">
                        <h6>${statusIcon} ${deviceName} - ${scheduleTime}</h6>
                        <div class="small text-muted">
                            <span class="badge bg-primary">${actionText}</span>
                            <span class="ms-2">Days: ${daysText}</span>
                        </div>
                    </div>
                    <button class="btn btn-sm btn-outline-danger" onclick="deleteSchedule('${escapedTaskId}')">
                        <i class="bi bi-trash"></i>
                    </button>
                </div>
            `;
            
            container.appendChild(item);
        }
    } catch (error) {
        showToast('Error loading schedules: ' + error.message, 'error');
    }
}

// Load auto restart
async function loadAutoRestart() {
    try {
        const response = await fetch(`${API_BASE}/auto-restart`);
        const data = await response.json();
        autoRestartData = data.auto_restart || {};
        
        const container = document.getElementById('auto-restart-list');
        container.innerHTML = '';
        
        const activeRestarts = Object.values(autoRestartData).filter(a => a.enabled !== false);
        
        if (activeRestarts.length === 0) {
            container.innerHTML = '<div class="empty-state"><i class="bi bi-arrow-repeat"></i><p>No auto restart configured</p></div>';
            return;
        }
        
        for (const [deviceName, settings] of Object.entries(autoRestartData)) {
            if (settings.enabled === false) continue;
            
            const item = document.createElement('div');
            item.className = 'auto-restart-item';
            
            const lastRun = settings.last_run ? new Date(settings.last_run * 1000).toLocaleString() : 'Never';
            const escapedDeviceName = escapeHtml(deviceName);
            const handlerDeviceName = escapeInlineHandlerArg(deviceName);
            const intervalText = escapeHtml(settings.interval_hours);
            const delayText = escapeHtml(settings.delay_seconds);
            const lastRunText = escapeHtml(lastRun);
            
            item.innerHTML = `
                <div class="d-flex justify-content-between align-items-start">
                    <div class="flex-grow-1">
                        <h6>✅ ${escapedDeviceName}</h6>
                        <div class="small text-muted">
                            <span>Interval: ${intervalText} hours</span>
                            <span class="ms-3">Delay: ${delayText}s</span>
                            <span class="ms-3">Last run: ${lastRunText}</span>
                        </div>
                    </div>
                    <button class="btn btn-sm btn-outline-danger" onclick="disableAutoRestart('${handlerDeviceName}')">
                        <i class="bi bi-x-circle"></i> Disable
                    </button>
                </div>
            `;
            
            container.appendChild(item);
        }
    } catch (error) {
        showToast('Error loading auto restart: ' + error.message, 'error');
    }
}

// Show schedule modal
function showScheduleModal() {
    updateDeviceSelects();
    const modal = new bootstrap.Modal(document.getElementById('addScheduleModal'));
    modal.show();
}

// Show add schedule modal
function showAddScheduleModal() {
    showScheduleModal();
}

// Submit add schedule
async function submitAddSchedule() {
    const form = document.getElementById('add-schedule-form');
    const formData = new FormData(form);
    
    const device = formData.get('device');
    const action = formData.get('action');
    const time = formData.get('time');
    const days = Array.from(formData.getAll('days')).map(d => parseInt(d));
    
    if (!device || !action || !time || days.length === 0) {
        showToast('Please fill all fields', 'error');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/schedules`, {
            method: 'POST',
            headers: withCsrfHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify({ device, action, time, days })
        });
        
        const result = await response.json();
        
        if (result.success) {
            showToast(result.message, 'success');
            bootstrap.Modal.getInstance(document.getElementById('addScheduleModal')).hide();
            form.reset();
            await loadSchedules();
        } else {
            showToast(`Error: ${result.message || 'Unknown error'}`, 'error');
        }
    } catch (error) {
        showToast('Error: ' + error.message, 'error');
    }
}

// Delete schedule
async function deleteSchedule(taskId) {
    if (!confirm('Delete this schedule?')) return;
    
    try {
        const response = await fetch(buildApiUrl(['schedules', taskId]), {
            method: 'DELETE',
            headers: withCsrfHeaders()
        });
        const data = await response.json();
        
        if (data.success) {
            showToast('Schedule deleted', 'success');
            await loadSchedules();
        }
    } catch (error) {
        showToast('Error: ' + error.message, 'error');
    }
}

// Show auto restart modal
function showAutoRestartModal() {
    updateDeviceSelects();
    const modal = new bootstrap.Modal(document.getElementById('autoRestartModal'));
    modal.show();
}

// Show set auto restart modal
function showSetAutoRestartModal() {
    showAutoRestartModal();
}

// Submit auto restart
async function submitAutoRestart() {
    const form = document.getElementById('auto-restart-form');
    const formData = new FormData(form);
    
    const device = formData.get('device');
    const interval = parseFloat(formData.get('interval'));
    
    if (!device || !interval) {
        showToast('Please fill all fields', 'error');
        return;
    }
    
    if (interval < 0.5 || interval > 168) {
        showToast('Interval must be between 0.5 and 168 hours', 'error');
        return;
    }
    
    try {
        const response = await fetch(buildApiUrl(['auto-restart', device]), {
            method: 'POST',
            headers: withCsrfHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify({ interval_hours: interval })
        });
        
        const result = await response.json();
        
        if (result.success) {
            showToast(result.message, 'success');
            bootstrap.Modal.getInstance(document.getElementById('autoRestartModal')).hide();
            form.reset();
            await loadAutoRestart();
        } else {
            showToast(`Error: ${result.message || 'Unknown error'}`, 'error');
        }
    } catch (error) {
        showToast('Error: ' + error.message, 'error');
    }
}

// Disable auto restart
async function disableAutoRestart(deviceName) {
    if (!confirm(`Disable auto restart for ${deviceName}?`)) return;
    
    try {
        const response = await fetch(buildApiUrl(['auto-restart', deviceName]), {
            method: 'DELETE',
            headers: withCsrfHeaders()
        });
        const data = await response.json();
        
        if (data.success) {
            showToast(data.message, 'success');
            await loadAutoRestart();
        }
    } catch (error) {
        showToast('Error: ' + error.message, 'error');
    }
}

// Show toast notification
function showToast(message, type = 'info') {
    const toast = document.getElementById('toast');
    const toastBody = document.getElementById('toast-body');
    
    toastBody.textContent = message;
    
    toast.className = 'toast';
    if (type === 'success') {
        toast.classList.add('bg-success', 'text-white');
    } else if (type === 'error') {
        toast.classList.add('bg-danger', 'text-white');
    } else {
        toast.classList.add('bg-info', 'text-white');
    }
    
    const bsToast = new bootstrap.Toast(toast);
    bsToast.show();
}

// Dark Mode Functions
function initDarkMode() {
    const darkMode = localStorage.getItem('darkMode') === 'true';
    if (darkMode) {
        document.body.classList.add('dark-mode');
        updateDarkModeIcon(true);
    } else {
        updateDarkModeIcon(false);
    }
}

function toggleDarkMode() {
    const isDark = document.body.classList.toggle('dark-mode');
    localStorage.setItem('darkMode', isDark);
    updateDarkModeIcon(isDark);
}

function updateDarkModeIcon(isDark) {
    const icon = document.getElementById('dark-mode-icon');
    if (icon) {
        icon.className = isDark ? 'bi bi-sun-fill' : 'bi bi-moon-fill';
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    initDarkMode();
    loadDevices();
    loadActivityLogs();
    
    // Auto refresh every 30 seconds
    setInterval(() => {
        refreshAll();
        loadActivityLogs();
        loadSchedules();
        loadAutoRestart();
    }, 30000);
});
