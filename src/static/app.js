// ============================================================================
// State Management
// ============================================================================

let currentUser = null;
let authToken = null;
let currentPermissions = null;

// ============================================================================
// Authentication
// ============================================================================

function getAuthToken() {
  return localStorage.getItem("authToken");
}

function setAuthToken(token) {
  authToken = token;
  localStorage.setItem("authToken", token);
}

function clearAuthToken() {
  authToken = null;
  localStorage.removeItem("authToken");
  currentUser = null;
}

function getAuthHeaders() {
  const token = getAuthToken();
  return {
    "Content-Type": "application/json",
    ...(token && { Authorization: `Bearer ${token}` })
  };
}

async function checkAuthentication() {
  const token = getAuthToken();
  if (!token) {
    showLoginPage();
    return false;
  }

  try {
    const response = await fetch("/auth/me", {
      headers: getAuthHeaders()
    });

    if (response.ok) {
      currentUser = await response.json();
      showAppPage();
      return true;
    } else {
      clearAuthToken();
      showLoginPage();
      return false;
    }
  } catch (error) {
    console.error("Auth check failed:", error);
    clearAuthToken();
    showLoginPage();
    return false;
  }
}

async function handleLogin(email, password) {
  try {
    const response = await fetch("/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password })
    });

    if (response.ok) {
      const data = await response.json();
      setAuthToken(data.access_token);
      currentUser = data.user;
      showAppPage();
      showNotification("Login successful!", "success");
    } else {
      const error = await response.json();
      showNotification(error.detail || "Login failed", "error");
    }
  } catch (error) {
    console.error("Login error:", error);
    showNotification("Network error", "error");
  }
}

async function handleRegister(email, password) {
  try {
    const response = await fetch("/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password })
    });

    if (response.ok) {
      const data = await response.json();
      setAuthToken(data.access_token);
      currentUser = data.user;
      showAppPage();
      showNotification("Registration successful!", "success");
    } else {
      const error = await response.json();
      showNotification(error.detail || "Registration failed", "error");
    }
  } catch (error) {
    console.error("Register error:", error);
    showNotification("Network error", "error");
  }
}

function handleLogout() {
  clearAuthToken();
  showLoginPage();
  showNotification("Logged out successfully", "success");
}

// ============================================================================
// Page Navigation
// ============================================================================

function showLoginPage() {
  document.getElementById("login-page").classList.remove("hidden");
  document.getElementById("app-page").classList.add("hidden");
}

function showAppPage() {
  document.getElementById("login-page").classList.add("hidden");
  document.getElementById("app-page").classList.remove("hidden");
  updateUserDisplay();
  updateAdminUI();
  loadActivities();
  loadClubs();
}

function updateUserDisplay() {
  if (currentUser) {
    document.getElementById("user-email-display").textContent = currentUser.email;
    document.getElementById("user-role-display").textContent = `[${currentUser.role}]`;
  }
}

function updateAdminUI() {
  const isAdmin = currentUser && (currentUser.role === "club_admin" || currentUser.role === "federation_admin");
  const isFederationAdmin = currentUser && currentUser.role === "federation_admin";
  
  // Show/hide admin tab
  const adminTabs = document.querySelectorAll(".admin-only");
  adminTabs.forEach(tab => {
    if (isAdmin) {
      tab.classList.remove("hidden");
    } else {
      tab.classList.add("hidden");
    }
  });
  
  // Show/hide federation-only sections
  const federationElements = document.querySelectorAll(".federation-admin-only");
  federationElements.forEach(el => {
    if (isFederationAdmin) {
      el.classList.remove("hidden");
    } else {
      el.classList.add("hidden");
    }
  });
}

// ============================================================================
// Notifications
// ============================================================================

function showNotification(message, type = "info") {
  const notification = document.getElementById("notification");
  const messageEl = document.getElementById("notification-message");
  
  messageEl.textContent = message;
  notification.className = `notification ${type}`;
  
  setTimeout(() => {
    notification.classList.add("hidden");
  }, 5000);
}

function closeNotification() {
  document.getElementById("notification").classList.add("hidden");
}

// ============================================================================
// API Helpers
// ============================================================================

async function apiCall(endpoint, options = {}) {
  const defaultHeaders = getAuthHeaders();
  const headers = { ...defaultHeaders, ...options.headers };
  
  try {
    const response = await fetch(endpoint, {
      ...options,
      headers
    });

    // Handle unauthorized
    if (response.status === 401) {
      clearAuthToken();
      showLoginPage();
      throw new Error("Unauthorized");
    }

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    return await response.json();
  } catch (error) {
    console.error(`API call failed: ${endpoint}`, error);
    throw error;
  }
}

// ============================================================================
// Activities
// ============================================================================

async function loadActivities() {
  try {
    const activities = await apiCall("/activities");
    
    const activitiesList = document.getElementById("activities-list");
    activitiesList.innerHTML = "";

    if (Object.keys(activities).length === 0) {
      activitiesList.innerHTML = "<p>No activities available.</p>";
      return;
    }

    Object.entries(activities).forEach(([activityId, activity]) => {
      const card = createActivityCard(activityId, activity);
      activitiesList.appendChild(card);
    });
  } catch (error) {
    console.error("Failed to load activities:", error);
    document.getElementById("activities-list").innerHTML = "<p>Failed to load activities.</p>";
  }
}

function createActivityCard(activityId, activity) {
  const card = document.createElement("div");
  card.className = "activity-card";

  const spotsLeft = activity.max_participants - activity.participants.length;
  const isSignedUp = activity.participants.includes(currentUser.email);

  const participantsHTML = activity.participants.length > 0
    ? `<div class="participants-section">
        <h5>Participants (${activity.participants.length}/${activity.max_participants}):</h5>
        <ul class="participants-list">
          ${activity.participants.map(email => 
            `<li>${email}</li>`
          ).join("")}
        </ul>
      </div>`
    : `<p><em>No participants yet</em></p>`;

  card.innerHTML = `
    <h4>${activity.name}</h4>
    <p>${activity.description}</p>
    <p><strong>Schedule:</strong> ${activity.schedule}</p>
    <p><strong>Availability:</strong> ${spotsLeft} spots left</p>
    <div class="participants-container">
      ${participantsHTML}
    </div>
    <div class="action-buttons">
      ${!isSignedUp && spotsLeft > 0 
        ? `<button class="btn-primary signup-btn" data-activity-id="${activityId}">Sign Up</button>`
        : ""
      }
      ${isSignedUp 
        ? `<button class="btn-secondary unregister-btn" data-activity-id="${activityId}">Unregister</button>`
        : ""
      }
      ${spotsLeft === 0 && !isSignedUp
        ? `<p class="full-text">Activity is full</p>`
        : ""
      }
    </div>
  `;

  // Add event listeners
  card.querySelector(".signup-btn")?.addEventListener("click", () => {
    signupForActivity(activityId);
  });
  card.querySelector(".unregister-btn")?.addEventListener("click", () => {
    unregisterFromActivity(activityId);
  });

  return card;
}

async function signupForActivity(activityId) {
  try {
    await apiCall(`/activities/${activityId}/signup`, { method: "POST" });
    showNotification("Signed up successfully!", "success");
    loadActivities();
  } catch (error) {
    showNotification(error.message, "error");
  }
}

async function unregisterFromActivity(activityId) {
  try {
    await apiCall(`/activities/${activityId}/unregister`, { method: "DELETE" });
    showNotification("Unregistered successfully!", "success");
    loadActivities();
  } catch (error) {
    showNotification(error.message, "error");
  }
}

// ============================================================================
// Clubs
// ============================================================================

async function loadClubs() {
  try {
    const clubs = await apiCall("/clubs");
    
    const clubsList = document.getElementById("clubs-list");
    clubsList.innerHTML = "";

    if (Object.keys(clubs).length === 0) {
      clubsList.innerHTML = "<p>No clubs available.</p>";
      return;
    }

    Object.entries(clubs).forEach(([clubId, club]) => {
      const card = createClubCard(clubId, club);
      clubsList.appendChild(card);
    });
  } catch (error) {
    console.error("Failed to load clubs:", error);
    document.getElementById("clubs-list").innerHTML = "<p>Failed to load clubs.</p>";
  }
}

function createClubCard(clubId, club) {
  const card = document.createElement("div");
  card.className = "club-card";

  const isMember = club.members.includes(currentUser.email);

  card.innerHTML = `
    <h4>${club.name}</h4>
    <p>${club.description}</p>
    <p><strong>Principal:</strong> ${club.principal}</p>
    <p><strong>Members:</strong> ${club.members.length}</p>
    <p><strong>Status:</strong> <span class="status-${club.status}">${club.status}</span></p>
    <div class="action-buttons">
      <button class="btn-primary view-club-btn" data-club-id="${clubId}">View Club Activities</button>
    </div>
  `;

  card.querySelector(".view-club-btn")?.addEventListener("click", () => {
    viewClubActivities(clubId, club.name);
  });

  return card;
}

async function viewClubActivities(clubId, clubName) {
  try {
    const activities = await apiCall(`/clubs/${clubId}/activities`);
    
    const modal = document.createElement("div");
    modal.className = "modal";
    modal.innerHTML = `
      <div class="modal-content">
        <h3>${clubName} - Activities</h3>
        <div id="modal-activities-list"></div>
        <button class="btn-secondary" onclick="this.closest('.modal').remove()">Close</button>
      </div>
    `;

    const activitiesList = modal.querySelector("#modal-activities-list");
    
    if (Object.keys(activities).length === 0) {
      activitiesList.innerHTML = "<p>No activities in this club.</p>";
    } else {
      Object.entries(activities).forEach(([activityId, activity]) => {
        const card = createActivityCard(activityId, activity);
        activitiesList.appendChild(card);
      });
    }

    document.body.appendChild(modal);
  } catch (error) {
    showNotification(error.message, "error");
  }
}

// ============================================================================
// Event Listeners - Login/Register
// ============================================================================

document.addEventListener("DOMContentLoaded", () => {
  // Tab navigation
  document.querySelectorAll(".nav-tab").forEach(tab => {
    tab.addEventListener("click", () => {
      const tabName = tab.dataset.tab;
      
      // Hide all tabs
      document.querySelectorAll(".tab-content").forEach(content => {
        content.classList.add("hidden");
      });
      
      // Remove active class
      document.querySelectorAll(".nav-tab").forEach(t => {
        t.classList.remove("active");
      });
      
      // Show selected tab and mark as active
      document.getElementById(tabName).classList.remove("hidden");
      tab.classList.add("active");
    });
  });

  // Login form
  document.getElementById("login-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const email = document.getElementById("login-email").value;
    const password = document.getElementById("login-password").value;
    await handleLogin(email, password);
  });

  // Register form
  document.getElementById("register-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const email = document.getElementById("register-email").value;
    const password = document.getElementById("register-password").value;
    await handleRegister(email, password);
  });

  // Switch between login and register
  document.getElementById("switch-to-register").addEventListener("click", () => {
    document.getElementById("login-container").classList.add("hidden");
    document.getElementById("register-container").classList.remove("hidden");
  });

  document.getElementById("switch-to-login").addEventListener("click", () => {
    document.getElementById("register-container").classList.add("hidden");
    document.getElementById("login-container").classList.remove("hidden");
  });

  // Logout button
  document.getElementById("logout-btn").addEventListener("click", handleLogout);

  // Check if already authenticated
  checkAuthentication();
});

