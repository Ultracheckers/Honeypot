<script lang="ts">
  import { invoke } from "@tauri-apps/api/core";
  import { goto } from "$app/navigation";
  import { onMount } from "svelte";
  import './app.css';

  let email = '';
  let username = '';
  let password = '';
  let activeTab = 'login';
  let error = '';
  let success = '';
  let loading = false;
  let rememberMe = false;

  onMount(async () => {
    // Check for existing session token on component mount
    const token = localStorage.getItem('token');
    const expiry = localStorage.getItem('expiry');
    
    if (token && expiry) {
      const expiryTime = parseInt(expiry);
      
      // Check if token hasn't expired
      if (new Date().getTime() < expiryTime) {
        loading = true;
        
        try {
          const response: any = await invoke('validate_token', { token });
          
          if (response.success) {
            // Valid token, set user ID and redirect to dashboard
            localStorage.setItem('user_id', response.user_id);
            goto('/dashboard');
          } else {
            // Invalid token, clear storage
            clearAuthStorage();
          }
        } catch (err) {
          console.error('Error validating token:', err);
          clearAuthStorage();
        } finally {
          loading = false;
        }
      } else {
        // Token expired, clear storage
        clearAuthStorage();
      }
    }
  });

  function clearAuthStorage() {
    localStorage.removeItem('token');
    localStorage.removeItem('expiry');
    localStorage.removeItem('user_id');
  }

  async function handleLogin() {
    if (!email || !password) {
      error = 'Please enter both email and password';
      success = '';
      return;
    }

    loading = true;
    error = '';
    
    try {
      const response: any = await invoke('login', { 
        credentials: { email, password },
        remember: rememberMe
      });
      
      if (response.success) {
        // Store user ID
        localStorage.setItem('user_id', response.user_id);
        
        // If remember me is checked and token is returned, store the session token
        if (rememberMe && response.token) {
          localStorage.setItem('token', response.token);
          localStorage.setItem('expiry', response.expiry.toString());
        }
        
        goto('/dashboard');
      } else {
        error = response.message;
        success = '';
      }
    } catch (err) {
      error = 'An error occurred during login';
      success = '';
      console.error(err);
    } finally {
      loading = false;
    }
  }

  async function handleRegister() {
    if (!email || email.length < 4) {
      error = 'Email must be at least 4 characters';
      return;
    }
    
    if (!password || password.length < 6) {
      error = 'Password must be at least 6 characters';
      return;
    }

    if (!username || username.length < 3) {
      error = 'Username must be at least 3 characters';
      return;
    }

    loading = true;
    error = '';
    
    try {
      const response: any = await invoke('register', { 
        credentials: { email, username, password } 
      });
      
      if (response.success) {
        // Auto-login or show success message
        activeTab = 'login';
        error = '';
        success = 'Registration successful! Please log in.';
      } else {
        error = response.message;
        success = '';
      }
    } catch (err) {
      error = 'An error occurred during registration';
      success = '';
      console.error(err);
    } finally {
      loading = false;
    }
  }

  function switchTab(tab: string) {
    activeTab = tab;
    email = '';
    password = '';
    error = '';
    success = '';
  }
</script>

<div class="min-h-screen flex items-center justify-center p-4 bg-gray-900">
  <div class="w-full max-w-md bg-gray-800 rounded-lg shadow-lg overflow-hidden border border-purple-300/20">
    <!-- Tabs -->
    <div class="flex border-b border-gray-700">
      <button 
        class="flex-1 py-3 font-medium text-center {activeTab === 'login' ? 'bg-gray-800 text-orange-400 border-b-2 border-orange-400' : 'text-gray-400 hover:text-gray-300 bg-gray-800'}"
        on:click={() => switchTab('login')}
      >
        Login
      </button>
      <button 
        class="flex-1 py-3 font-medium text-center {activeTab === 'register' ? 'bg-gray-800 text-orange-400 border-b-2 border-orange-400' : 'text-gray-400 hover:text-gray-300 bg-gray-800'}"
        on:click={() => switchTab('register')}
      >
        Register
      </button>
    </div>

    <div class="p-6">
      <!-- App Logo/Title -->
      <div class="text-center mb-6">
        <h2 class="text-2xl font-bold text-gray-200">Honeypot Dashboard</h2>
        
      </div>

      {#if activeTab === 'login'}
        <!-- Login Form -->
        <form on:submit|preventDefault={handleLogin} class="space-y-4">
          <div>
            <label for="email" class="block text-sm font-medium text-gray-300 mb-1">Email</label>
            <input
              id="email"
              type="email"
              bind:value={email}
              placeholder="Enter your email"
              class="w-full px-4 py-2 rounded bg-gray-700 border border-gray-600 focus:outline-none focus:ring-2 focus:ring-orange-400 text-gray-200 placeholder-gray-400"
              required
            />
          </div>
          <div>
            <label for="password" class="block text-sm font-medium text-gray-300 mb-1">Password</label>
            <input
              id="password"
              type="password"
              bind:value={password}
              placeholder="Enter your password"
              class="w-full px-4 py-2 rounded bg-gray-700 border border-gray-600 focus:outline-none focus:ring-2 focus:ring-orange-400 text-gray-200 placeholder-gray-400"
              required
            />
          </div>
          <div class="flex items-center justify-between">
            <div class="flex items-center">
              <input 
                id="remember" 
                type="checkbox" 
                bind:checked={rememberMe}
                class="h-4 w-4 text-orange-500 focus:ring-orange-400 border-gray-600 rounded bg-gray-700" 
              />
              <label for="remember" class="ml-2 block text-sm text-gray-300">Remember me</label>
            </div>
          </div>
          <button
            type="submit"
            disabled={loading}
            class="w-full bg-orange-600 hover:bg-orange-700 text-white font-medium py-2 px-4 rounded transition-colors focus:outline-none focus:ring-2 focus:ring-purple-400 focus:ring-offset-2 focus:ring-offset-gray-800 mt-2 {loading ? 'opacity-70 cursor-not-allowed' : ''}"
          >
            {loading ? 'Signing in...' : 'Sign in'}
          </button>
        </form>
      {:else}
        <!-- Register Form -->
        <form on:submit|preventDefault={handleRegister} class="space-y-4">
          <div>
            <label for="reg-email" class="block text-sm font-medium text-gray-300 mb-1">Email</label>
            <input
              id="reg-email"
              type="email"
              bind:value={email}
              placeholder="Enter your email"
              class="w-full px-4 py-2 rounded bg-gray-700 border border-gray-600 focus:outline-none focus:ring-2 focus:ring-orange-400 text-gray-200 placeholder-gray-400"
              required
            />
          </div>
          <div>
            <label for="reg-username" class="block text-sm font-medium text-gray-300 mb-1">Username</label>
            <input
              id="reg-username"
              type="username"
              bind:value={username}
              placeholder="Enter your username"
              class="w-full px-4 py-2 rounded bg-gray-700 border border-gray-600 focus:outline-none focus:ring-2 focus:ring-orange-400 text-gray-200 placeholder-gray-400"
              required
            />
          </div>
          <div>
            <label for="reg-password" class="block text-sm font-medium text-gray-300 mb-1">Password</label>
            <input
              id="reg-password"
              type="password"
              bind:value={password}
              placeholder="Create a password (min. 6 characters)"
              class="w-full px-4 py-2 rounded bg-gray-700 border border-gray-600 focus:outline-none focus:ring-2 focus:ring-orange-400 text-gray-200 placeholder-gray-400"
              required
              minlength="6"
            />
            <p class="mt-1 text-xs text-gray-400">Password must be at least 6 characters long</p>
          </div>
          <button
            type="submit"
            disabled={loading}
            class="w-full bg-orange-600 hover:bg-orange-700 text-white font-medium py-2 px-4 rounded transition-colors focus:outline-none focus:ring-2 focus:ring-orange-400 focus:ring-offset-2 focus:ring-offset-gray-800 mt-2 {loading ? 'opacity-70 cursor-not-allowed' : ''}"
          >
            {loading ? 'Creating account...' : 'Create account'}
          </button>
        </form>
      {/if}
      
      {#if error}
        <div class="mt-4 p-3 rounded bg-red-900/50 border border-red-700 text-red-200 text-sm">
          {error}
        </div>
      {/if}
      {#if success}
        <div class="mt-4 p-3 rounded bg-green-900/50 border border-green-700 text-green-200 text-sm">
        {success}
        </div>
      {/if}
    </div>
  </div>
</div>