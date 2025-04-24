<script lang="ts">
    import { invoke } from "@tauri-apps/api/core";
    import { goto } from "$app/navigation";
    import '../app.css';
    // Import any additional dependencies here

  
    function switchToDashboard() {
        goto("/dashboard")
    }
  </script>

  <h1>Settings</h1>
  <button on:click={switchToDashboard}>Dashboard</button>