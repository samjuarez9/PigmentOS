// Trial Tracking for PigmentOS Dashboard
// Add this script to index.html to track trial status

import { getAuth, onAuthStateChanged } from "https://www.gstatic.com/firebasejs/10.7.1/firebase-auth.js";
import { getFirestore, doc, getDoc } from "https://www.gstatic.com/firebasejs/10.7.1/firebase-firestore.js";
import { initializeApp } from "https://www.gstatic.com/firebasejs/10.7.1/firebase-app.js";

// Firebase config (already in your index.html, this is a reference)
const firebaseConfig = {
    apiKey: "AIzaSyCEtjs3kYaB7usZjplg797NYtM4MFIdm7g",
    authDomain: "pigmentos-49d50.firebaseapp.com",
    projectId: "pigmentos-49d50",
    storageBucket: "pigmentos-49d50.firebasestorage.app",
    messagingSenderId: "52957674554",
    appId: "1:52957674554:web:2a3b295c23978980a6c903",
    measurementId: "G-RDE19D05G2"
};

const app = initializeApp(firebaseConfig);
const auth = getAuth(app);
const db = getFirestore(app);

// Check subscription status on page load
onAuthStateChanged(auth, async (user) => {
    if (!user) {
        // Not logged in - redirect to login
        window.location.href = '/login.html';
        return;
    }

    try {
        // Get user data from Firestore
        const userDoc = await getDoc(doc(db, "users", user.uid));

        if (!userDoc.exists()) {
            console.log("No user data found, allowing access");
            return;
        }

        const userData = userDoc.data();
        const trialStartDate = userData.trialStartDate?.toDate();

        // Call backend to check subscription status
        const response = await fetch('/api/subscription-status', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                email: user.email,
                trial_start_date: trialStartDate?.toISOString()
            })
        });

        const status = await response.json();

        if (!status.has_access) {
            // Trial expired and no subscription
            window.location.href = '/upgrade.html';
            return;
        }

        // Show trial banner if trialing
        if (status.status === 'trialing') {
            showTrialBanner(status.days_remaining);
        }

    } catch (error) {
        console.error('Subscription check error:', error);
    }
});

function showTrialBanner(daysRemaining) {
    const banner = document.createElement('div');
    banner.id = 'trial-banner';
    banner.style.cssText = `
position: fixed;
top: 0;
left: 0;
width: 100 %;
background: linear - gradient(90deg, #9D4EDD, #7B2CBF);
color: white;
text - align: center;
padding: 10px;
font - family: 'VT323', monospace;
font - size: 18px;
z - index: 10000;
box - shadow: 0 2px 10px rgba(0, 0, 0, 0.3);
`;

    banner.innerHTML = `
        🎁 Free Trial: ${daysRemaining} days remaining
    < a href = "/upgrade.html" style = "color: #00FFFF; text-decoration: underline; margin-left: 20px;" >
        Upgrade Now →
        </a >
    `;

    document.body.prepend(banner);

    // Adjust page content to account for banner
    document.body.style.paddingTop = '40px';
}
