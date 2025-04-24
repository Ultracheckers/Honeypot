<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { invoke } from "@tauri-apps/api/core";
  import { goto } from "$app/navigation";
  import '../app.css';

  let logs = [];
  let devices = [];
  let expandedDevice = null;
  let loading = true;
  let refreshInterval: number;
  let refreshing = false;

  interface MongoDbDevice {
    _id?: { $oid: string };
    device_id: string;
    status: string;
    ip_address: string;
    location: string;
    type: string;
    created_at?: { $date: { $numberLong: string } };
    last_seen?: { $date: { $numberLong: string } };
  }

  interface MongoDbLog {
    _id?: { $oid: string };
    dst_host: string;
    dst_port: { $numberInt: string };
    local_time: string;
    local_time_adjusted: string;
    logdata: any;
    logtype: { $numberInt: string };
    node_id: string;
    src_host: string;
    src_port: { $numberInt: string };
    utc_time: string;
    device_id: string;
  }


function formatTimestamp(timestamp: string): string {
  try {

    const [datePart, timePart] = timestamp.split(' ');
    const [year, month, day] = datePart.split('-').map(Number);
    const [hours, minutes, seconds] = timePart.split(':').map(val => {
      if (val.includes('.')) {
        return parseFloat(val);
      }
      return parseInt(val, 10);
    });
    

    const date = new Date(Date.UTC(
      year,
      month - 1, 
      day,
      hours,
      minutes,
      Math.floor(seconds), 
      (seconds % 1) * 1000
    ));
    
    return new Intl.DateTimeFormat(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: 'numeric',
      second: 'numeric',
      hour12: true
    }).format(date);
  } catch (e) {
    console.error("Error formatting timestamp:", e, timestamp);
    return timestamp;
  }
}
    
  
  function extractMessage(log: MongoDbLog): { 
    type: string, 
    description: string,
    details: string
  } {
    // Default values
    let type = "Unknown";
    let description = "Unknown log event";
    let details = "";
    
    try {
      // Determine log type
      if (log.logtype) {
        const logTypeNum = parseInt(log.logtype.$numberInt || log.logtype.toString());
        
        // Convert numeric log types to human-readable format
        switch (logTypeNum) {
          // FTP logs
          case 2000:
            type = "FTP";
            description = "Login attempt";
            break;
          case 2001:
            type = "FTP";
            description = "Authentication initiated";
            break;
            
          // HTTP logs  
          case 3000:
            type = "HTTP";
            description = "GET request";
            break;
          case 3001:
            type = "HTTP";
            description = "Login attempt";
            break;
          case 3002:
            type = "HTTP";
            description = "Unimplemented method";
            break;
          case 3003:
            type = "HTTP";
            description = "Redirect";
            break;
            
          // SSH logs
          case 4000:
            type = "SSH";
            description = "New connection";
            break;
          case 4001:
            type = "SSH";
            description = "Remote version sent";
            break;
          case 4002:
            type = "SSH";
            description = "Login attempt";
            break;
            
          default:
            type = "Other";
            description = `Log event (${logTypeNum})`;
        }
      }
      
      // Extract additional details if available
      if (log.logdata && log.logdata.msg) {
        if (log.logdata.msg.logdata) {
          details = log.logdata.msg.logdata;
        } else if (typeof log.logdata.msg === 'string') {
          details = log.logdata.msg;
        } else {
          details = JSON.stringify(log.logdata.msg);
        }
      }
      
      return { type, description, details };
    } catch (e) {
      return { 
        type: "Error", 
        description: "Error parsing log", 
        details: "Failed to parse log message" 
      };
    }
  }
  
function getStatusDisplay(device: MongoDbDevice): { text: string, isOnline: boolean } {
  if (device.last_seen && device.last_seen.$date && device.last_seen.$date.$numberLong) {
    const lastSeenTimestamp = new Date(parseInt(device.last_seen.$date.$numberLong));
    
    const fiveMinutesAgo = new Date(Date.now() - 5 * 60 * 1000);
    
    if (lastSeenTimestamp > fiveMinutesAgo) {
      return { text: "Online", isOnline: true };
    } else {
      const minutesSinceLastSeen = Math.floor((Date.now() - lastSeenTimestamp.getTime()) / (60 * 1000));
      return { text: `Offline (${minutesSinceLastSeen}m)`, isOnline: false };
    }
  }
  
  if (!device.status) return { text: "Unknown", isOnline: false };
  
  const status = device.status.toLowerCase();
  if (status === "online" || status === "active") {
    return { text: "Online", isOnline: true };
  } else {
    return { text: "Offline", isOnline: false };
  }
}

  function getDeviceName(device: MongoDbDevice): string {
    return `${device.device_id}`;
  }

  async function fetchUserData(isInitialLoad = false) {
    try {
      if (isInitialLoad) {
        loading = true;
      } else {
        refreshing = true;
      }
      
      const user_id = localStorage.getItem('user_id');
      
      if (!user_id) {
        goto('/');
        return;
      }

      console.log("Fetching data with user_id:", user_id);

      try {
        const userDevices = await invoke('get_user_devices', { userId: user_id });
        console.log("Devices fetched:", userDevices);
        
        if (userDevices && Array.isArray(userDevices)) {
          devices = userDevices as MongoDbDevice[];
        }
      } catch (error) {
        console.error("Error fetching devices:", error);
      }
      
      try {
        const userLogs = await invoke('get_user_logs', { userId: user_id });
        console.log("Logs fetched:", userLogs);
        
        if (userLogs && Array.isArray(userLogs)) {
          logs = userLogs as MongoDbLog[];
        }
      } catch (error) {
        console.error("Error fetching logs:", error);
      }
      
    } catch (error) {
      console.error('Error in fetchUserData:', error);
    } finally {
      loading = false;
      refreshing = false;
    }
  }

  function getDeviceLogs(deviceId: string): MongoDbLog[] {
    return logs
    .filter(log => log.device_id === deviceId)
    .sort((a, b) => {
      const dateA = new Date(a.utc_time).getTime();
      const dateB = new Date(b.utc_time).getTime();
      return dateB - dateA;  
    });
}

  function getDeviceById(deviceId: string): MongoDbDevice | undefined {
    return devices.find(device => device.device_id === deviceId);
  }

  function getRecentLogs(): MongoDbLog[] {
    return [...logs]
      .sort((a, b) => {
        const dateA = new Date(a.utc_time).getTime();
        const dateB = new Date(b.utc_time).getTime();
        return dateB - dateA;
      })
      .slice(0, 5);
  }

  onMount(async () => {
    await fetchUserData(true);
    refreshInterval = setInterval(() => fetchUserData(false), 60000);
  });
  
  onDestroy(() => {
    if (refreshInterval) {
      clearInterval(refreshInterval);
    }
  });

  function toggleDevice(deviceId: string) {
    expandedDevice = expandedDevice === deviceId ? null : deviceId;
  }

  async function handleLogout() {
    const user_id = localStorage.getItem('user_id');

    if (user_id) {
      try {
        await invoke('logout', { user_id: user_id });
      } catch (err) {
        console.error('Error during logout:', err);
      }
    }

    localStorage.removeItem('user_id');
    localStorage.removeItem('token');
    localStorage.removeItem('expiry');
  
    goto('/');
  }
</script>

<div class="min-h-screen bg-gradient-to-br from-gray-900 to-gray-800 p-6 font-sans">
  <div class="max-w-5xl mx-auto">
    <!-- Header -->
    <header class="flex justify-between items-center mb-8">
      <h1 class="text-4xl font-extrabold text-gray-100 tracking-tight">
        Dashboard
      </h1>
      <button 
        on:click={handleLogout}
        class="bg-gradient-to-r from-orange-500 to-orange-600 text-white px-5 py-2 rounded-full shadow-md hover:from-orange-600 hover:to-orange-700 transition-all duration-300"
      >
        Logout
      </button>
    </header>

    {#if loading && devices.length === 0 && logs.length === 0}
      <div class="bg-gray-800/80 backdrop-blur-sm rounded-2xl shadow-xl p-8 border border-orange-500/20 flex justify-center items-center min-h-[200px]">
        <div class="flex items-center space-x-3">
          <svg class="animate-spin h-8 w-8 text-orange-500" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
          <p class="text-gray-200 text-lg">Loading data...</p>
        </div>
      </div>
    {:else}
      <section class="bg-gray-800/80 backdrop-blur-sm rounded-2xl shadow-xl p-8 mb-8 border border-orange-500/20">
        <div class="flex justify-between items-center mb-6">
          <h2 class="text-2xl font-semibold text-gray-100">Recent Logs</h2>
          {#if refreshing}
            <span class="text-sm text-orange-400 animate-pulse">Refreshing...</span>
          {/if}
        </div>
        {#if logs && logs.length > 0}
          <div class="space-y-4">
            {#each getRecentLogs() as log}
              {@const logInfo = extractMessage(log)}
              {@const device = getDeviceById(log.device_id)}
              <div class="bg-gray-700/50 p-4 rounded-xl border border-gray-600/30 hover:bg-gray-700/70 transition-colors duration-200">
                <div class="flex justify-between items-center mb-2">
                  <div class="flex items-center space-x-3">
                    <!-- Type badge -->
                    <span class={`px-2 py-1 rounded text-xs font-medium ${
                      logInfo.type === 'SSH' ? 'bg-purple-500/20 text-purple-300' : 
                      logInfo.type === 'HTTP' ? 'bg-blue-500/20 text-blue-300' : 
                      logInfo.type === 'FTP' ? 'bg-green-500/20 text-green-300' : 
                      'bg-gray-500/20 text-gray-300'
                    }`}>
                      {logInfo.type}
                    </span>
                    <span class="text-gray-200 font-medium">{logInfo.description}</span>
                  </div>
                  <span class="text-orange-400 text-sm font-medium">Device: {log.device_id}</span>
                </div>
                
                <div class="grid grid-cols-1 md:grid-cols-3 gap-2 mt-3 text-sm">
                  <div class="text-gray-400">
                    <span class="font-medium text-gray-300">Source IP:</span> {log.src_host}:{log.src_port?.$numberInt || log.src_port}
                  </div>
                  <div class="text-gray-400">
                    <span class="font-medium text-gray-300">Device IP:</span> {device?.ip_address || 'Unknown'}:{log.dst_port?.$numberInt || log.dst_port}
                  </div>
                  <div class="text-gray-400">
                    <span class="font-medium text-gray-300">Time:</span> {formatTimestamp(log.utc_time)}
                  </div>
                </div>
                
                {#if logInfo.details}
                  <div class="mt-2 pt-2 border-t border-gray-600/30">
                    <p class="text-gray-200 leading-relaxed">{logInfo.details}</p>
                  </div>
                {/if}
              </div>
            {/each}
          </div>
        {:else}
          <p class="text-gray-400 text-center py-6 text-lg">No logs available</p>
        {/if}
      </section>
      <section class="bg-gray-800/80 backdrop-blur-sm rounded-2xl shadow-xl p-8 border border-orange-500/20">
        <div class="flex justify-between items-center mb-6">
          <h2 class="text-2xl font-semibold text-gray-100">Devices</h2>
          <span class="text-sm text-gray-400">{devices.length} device(s)</span>
        </div>
        
        <div class="overflow-x-auto">
          {#if devices.length > 0}
            <table class="w-full text-left text-gray-300">
              <thead class="text-xs uppercase bg-gray-700/50 text-gray-400">
                <tr>
                  <th scope="col" class="px-6 py-4">Device Name</th>
                  <th scope="col" class="px-6 py-4">Device Location</th>
                  <th scope="col" class="px-6 py-4">IP Address</th>
                  <th scope="col" class="px-6 py-4">Status</th>
                  <th scope="col" class="px-6 py-4"></th>
                </tr>
              </thead>
              <tbody>
                {#each devices as device}
                  {@const status = getStatusDisplay(device)}
                  <tr class="border-b border-gray-700/50 hover:bg-gray-700/30 transition-colors duration-200">
                    <th scope="row" class="px-6 py-4 font-medium text-gray-100">
                      {getDeviceName(device)}
                    </th>
                    <td class="px-6 py-4">
                      {device.location || 'Unknown'}
                    </td>
                    <td class="px-6 py-4">
                      {device.ip_address || 'Unknown'}
                    </td>
                    <td class="px-6 py-4">
                      <div class="flex items-center">
                        <div class="h-3 w-3 rounded-full {status.isOnline ? 'bg-green-400' : 'bg-red-400'} mr-2"></div>
                        <span class="text-gray-200">{status.text}</span>
                      </div>
                    </td>
                    <td class="px-6 py-4">
                      <button 
                        on:click={() => toggleDevice(device.device_id)} 
                        class="font-medium text-orange-400 hover:text-orange-300 transition-colors duration-200"
                      >
                        {expandedDevice === device.device_id ? 'Hide Logs' : 'View Logs'}
                      </button>
                    </td>
                  </tr>
                  {#if expandedDevice === device.device_id}
                  {@const deviceLogs = getDeviceLogs(device.device_id)}
                  <tr>
                    <td colspan="5" class="px-6 py-4">
                      <div class="space-y-4 bg-gray-900/30 p-4 rounded-xl transition-all duration-300">
                        {#if deviceLogs && deviceLogs.length > 0}
                          {#each deviceLogs as log}
                            {@const logInfo = extractMessage(log)}
                            {@const deviceInfo = getDeviceById(log.device_id)}
                            <div class="bg-gray-700/50 p-4 rounded-lg border border-gray-600/30">
                              <div class="flex justify-between items-center mb-2">
                                <div class="flex items-center space-x-3">
                                  <!-- Type badge -->
                                  <span class={`px-2 py-1 rounded text-xs font-medium ${
                                    logInfo.type === 'SSH' ? 'bg-purple-500/20 text-purple-300' : 
                                    logInfo.type === 'HTTP' ? 'bg-blue-500/20 text-blue-300' : 
                                    logInfo.type === 'FTP' ? 'bg-green-500/20 text-green-300' : 
                                    'bg-gray-500/20 text-gray-300'
                                  }`}>
                                    {logInfo.type}
                                  </span>
                                  <span class="text-gray-200 font-medium">{logInfo.description}</span>
                                </div>
                                <span class="text-gray-400 text-sm">{formatTimestamp(log.utc_time)}</span>
                              </div>
                              
                              <div class="grid grid-cols-1 md:grid-cols-2 gap-2 mt-3 text-sm">
                                <div class="text-gray-400">
                                  <span class="font-medium text-gray-300">Source IP:</span> {log.src_host}:{log.src_port?.$numberInt || log.src_port}
                                </div>
                                <div class="text-gray-400">
                                  <span class="font-medium text-gray-300">Device IP:</span> {deviceInfo?.ip_address || 'Unknown'}:{log.dst_port?.$numberInt || log.dst_port}
                                </div>
                              </div>
                              
                              {#if logInfo.details}
                                <div class="mt-2 pt-2 border-t border-gray-600/30">
                                  <p class="text-gray-200 leading-relaxed">{logInfo.details}</p>
                                </div>
                              {/if}
                            </div>
                          {/each}
                        {:else}
                          <p class="text-gray-400 text-sm text-center py-4">No logs available for this device</p>
                        {/if}
                      </div>
                    </td>
                  </tr>
                  {/if}
                {/each}
              </tbody>
            </table>
          {:else}
            <p class="text-gray-400 text-center py-6 text-lg">No devices available</p>
          {/if}
        </div>
      </section>
    {/if}
  </div>
</div>