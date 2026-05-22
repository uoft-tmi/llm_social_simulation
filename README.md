# **project name**


## **Table of Contents**

- [Project Summary](#project-summary)
- [Features](#features)
- [Installation Instructions](#installation-instructions)
- [Usage Guide](#usage-guide)
- [Architecture Overview](#architecture-overview)
- [Feedback](#feedback)
- [Contributing](#contributing)
- [License](#license)

---

## Project Summary

**LLM Social Simulation** is a multi-agent research sandbox for studying how language-model agents behave in shared social environments. The project simulates agents that can move, gather resources, communicate, form reputations, and participate in governance decisions inside controllable virtual worlds.

The system supports both **rule-based agents** and **LLM-powered agents**, allowing users to compare simple baseline strategies with language-model-driven decision making. Each simulation produces replayable traces, events, and metrics that can be visualized through a web-based research viewer.

### What This Project Does

LLM Social Simulation provides a platform where users can:

- Run multi-agent simulations in configurable environments
- Compare rule-based agents with LLM-powered agents
- Study cooperation, competition, trust, reputation, communication, and governance
- Replay simulations tick by tick through a frontend visualization
- Inspect agent actions, observations, decisions, and world-level metrics
- Test how different rules, incentives, and social structures affect collective outcomes

The project currently includes two main environments:

1. **Open Resources**  
   A commons-style resource game where agents harvest from and contribute to a shared resource pool.

2. **Open World**  
   A small town simulation where agents move between zones, gather resources, communicate locally or publicly, build reputations, and vote on governance proposals.

### Why This Project Was Made

Large language models are increasingly used as autonomous agents, but their behavior in social environments is still difficult to understand. Simple one-agent benchmarks cannot fully show how LLM agents cooperate, deceive, follow rules, respond to incentives, or influence each other through communication.

This project was created to explore questions such as:

- Can LLM agents cooperate in a shared environment?
- How does communication affect trust and group behavior?
- Can agents form useful reputations based on observed actions?
- How do governance rules change social outcomes?
- How do LLM agents compare with rule-based agents under the same conditions?

### Problem It Solves

- **Lack of controllable LLM social experiments**  
  Provides a structured environment where agent behavior can be tested repeatedly.

- **Difficulty analyzing multi-agent behavior**  
  Records replayable traces, events, metrics, and decisions for later inspection.

- **Weak separation between LLM output and world state**  
  Keeps the world state as the source of truth. LLMs only propose actions; the simulation engine validates and applies them.

- **Hard-to-debug LLM agents**  
  Includes guardrails, structured prompts, validation, fallback behavior, and diagnostic information.

- **Need for comparison baselines**  
  Supports both LLM policies and rule-based policies so behavior can be compared.

---
## **Features**

### **Spotify Integration**
- **Automatic Profile Creation**: Connects to your Spotify account to automatically populate your music preferences
- **Top Tracks Analysis**: Analyzes your most-listened tracks, genres, and artists to understand your music taste

**Example (programmatic usage & output)**
```java
// Example: fetch Spotify data used for matching (pseudo-usage)
SpotifyInterface spotify = session.getSpotify(); // Get the SpotifyInterface instance from the current user session
spotify.initSpotify(); // Start Spotify authentication process (opens browser for user login)
spotify.pullUserData(); // Retrieve the logged-in Spotify user's ID and display name
spotify.pullTopArtistsAndGenres(); // Retrieve the user's top artists and genres from Spotify
spotify.pullTopTracks(); // Retrieve the user's top tracks from Spotify

System.out.println("User: " + spotify.getUserName() + " (" + spotify.getUserId() + ")");
System.out.println("Top Artists: " + spotify.getTopArtists());
System.out.println("Top Tracks: " + spotify.getTopTracks());
System.out.println("Top Genres: " + spotify.getTopGenres());
```
**Output**
```text
User: Alice (user_12345)
Top Artists: [Taylor Swift, The Weeknd, Coldplay, Joji, Ed Sheeran]
Top Tracks: [Cardigan, Blinding Lights, Yellow, Glimpse of Us, Shivers]
Top Genres: [pop, indie pop, alt-pop, pop, pop rock, indie pop]
```

### **User Matching System**
- **Artist & Genre Matching**: Compares users’ favourite artists and genres
- **Compatibility Scoring**: Computes a numeric score from overlap in artists and genres
- **Filtered Matching**: Set preferred age range, gender, and location for potential matches

**Example (programmatic usage & output)**
```java
// Assume we have a logged-in session
UserSession session = ...;

// Get current user and all registered users
User currentUser = session.getUser();
List<User> allUsers = session.getAllUsers();

// Set the current user's match filter
SetupMatchFilterInteractor setupFilter = new SetupMatchFilterInteractor(
        filter -> System.out.println("Filter saved: " + filter),
        session
);
setupFilter.setupFilter(20, 30, "female", "Toronto");

// Find candidates that pass both users' filters
MatchService matchService = new MatchServiceImpl(); // no-arg constructor
List<User> candidates = matchService.findMatches(currentUser, allUsers);

// Display compatibility scores (calculated separately)
MatchCalculatorImpl calculator = new MatchCalculatorImpl();
System.out.println("=== Match Candidates ===");
for (User u : candidates) {
    int score = calculator.calculateCompatibilityScore(currentUser, u);
    System.out.println(u.getName() + " — " + score + "%");
}
```
**Output**
```text
Filter saved: MatchFilter{minAge=20, maxAge=30, gender='female', location='Toronto'}
=== Match Candidates ===
Diana — 92%
Eric — 87%
Alice — 85%
```

### **Matching Interaction**
- **Profile Browsing** – View profiles of potential matches, including name, age, location, biography, and compatibility score in the matchingroom  
- **Connect or Skip** – Choose to connect with or skip a potential match. Clicking **Connect** sends a friend request to the other user's mailbox. Clicking **Skip** removes the other user from your matching queue
- **Handle Incoming Requests** – Receive friend requests from other users in your mailbox. Click **Accept** to add them to your friend list, or **Decline** to remove them from your matching queue

**Example (programmatic usage & output)**

```java
// Assume we have a logged-in session and a candidate user
UserSession session = ...;
User matchedUser = ...;  // a user from your match candidates

// Connect flow (non‑mutual): sends a friend request to matchedUser
matcher.connect(session, matchedUser);

// Skip flow: removes the user from incoming/outgoing match queues
matcher.skip(session, matchedUser);

// Simulate that 'matchedUser' has already sent a request to 'currentUser'
User currentUser = session.getUser();
matchDataAccessObject.getOutgoingFriendRequest(matchedUser).add(currentUser);

// Now connect — should immediately become friends
matcher.connect(session, matchedUser);
```
**Output**
```text
[Presenter] Friend request sent to Diana
[Presenter] You are now friends with Diana
```
Note: visualization will be shown in the usage session.

### **Social Features**
- **Post Creation**: Share your thoughts about music, concerts, or new music discoveries
- **Comment System**: Engage with other users' posts
- **Friend Requests**: Send and manage friend requests
- **Blocking System**: Block users you don't want to interact with
  Note: detailed example related to social features will be displayed in the Usage Guide session.

### **User Profiles**
- **Comprehensive Profiles**: Age, location, bio, and music preferences
- **Profile Pictures**: Upload and manage profile images
- **Music Statistics**: View your top artists, tracks, and genres
- **Privacy Controls**: Manage who can see your profile
**Example**
<img width="1049" height="792" alt="image" src="https://github.com/user-attachments/assets/a0617472-16ed-45c8-bb8c-eea85406b813" />

### **Advanced Features**
- **Responsive UI**: Clean, intuitive Java Swing interface

---

## **Installation Instructions**

### **Prerequisites**

Before installing **S-Buddify**, make sure you have the following software installed:

- **Java Development Kit (JDK) 17** or higher  
  - Download: [Oracle JDK](https://www.oracle.com/java/technologies/downloads/) or [Eclipse Adoptium OpenJDK](https://adoptium.net/)  

- **Apache Maven 3.6+**  
  - Download: [Apache Maven](https://maven.apache.org/download.cgi)  

- **Spotify Account**  
  - Required for music analysis features  
  - Both free and premium accounts are supported  
  - Sign up: [Spotify Website](https://www.spotify.com/)

### **Installation Steps**

1. **Clone the Repository**
   ```bash
   git clone https://github.com/your-username/csc207-project.git
   cd csc207-project
   ```

2. **Verify Java Installation**
   ```bash
   java -version
   # Should show Java version 17 or higher
   ```

3. **Verify Maven Installation**
   ```bash
   mvn -version
   # Should show Maven version 3.6 or higher
   ```

4. **Build application**
   ```
   mvn package
   ```

4. **Run application**
   ```
   java -jar target/csc207-project-1.0-SNAPSHOT.jar 
   ```
### **Common Installation Issues & Fixes**

| Issue | Cause | Solution |
|-------|-------|----------|
| `java: command not found` | Java not installed or not in PATH | Install JDK 17+ and ensure `JAVA_HOME` and `PATH` are set correctly |
| `mvn: command not found` | Maven not installed or not in PATH | Install Maven and add it to your PATH |
| `UnsupportedClassVersionError` | Java version too low | Upgrade to JDK 17 or higher |
| Spotify login window doesn’t open | Default browser misconfigured | Set a default browser in your OS settings and try again |
| `java.net.UnknownHostException` | No internet connection | Check your network and retry |


### **Example: Full Installation on macOS**

1. **Install Java 17 via Homebrew:**
    ```bash
    brew install openjdk@17
    brew link --force --overwrite openjdk@17
    ```

2. **Install Maven:**
    ```bash
    brew install maven
    ```

3. **Clone and Build:**
    ```bash
    git clone https://github.com/your-username/csc207-project.git
    cd csc207-project
    mvn package
    ```

4. **Run:**
    ```bash
    java -jar target/csc207-project-1.0-SNAPSHOT.jar
    ```
---

## **Usage Guide**
### **Getting Started**

1. **Launch the Application**
   - Run the application by running Main
   - The window will appear with Login View
     
2. **Connect Spotify**
    - Click "Continue With Spotify"
    - A browser window will open for Spotify authorization
    - Login to Spotify and grant permissions to access your listening data
![Login Demo](https://github.com/bgkillas/csc207-project/blob/main/assets/login.gif)

4. **Setup Your Profile**
   - Sign up and login
   - Fill in your basic information (name, age, location)
   - Upload a profile picture to your account (Optional)
![Set Up Profile Demo](https://github.com/bgkillas/csc207-project/blob/main/assets/setupprofile.gif)

5. **Set Up Match Filters**
   - Configure your matching preferences (age range, location, etc.)
   - These filters will help find compatible matches
![Set Up Match Filter](https://github.com/bgkillas/csc207-project/blob/main/assets/matchfilter.gif)

### **Using the Matching System**

1. **Access Matching Room**
   - Navigate to the "Matching" section
   - View potential matches based on your preferences
   - Connect or Skip potential matches

2. **Browse Profiles**
   - See compatibility scores with each potential match
   - View the matched user's basic info
![Matching Flow Demo](https://github.com/bgkillas/csc207-project/blob/main/assets/matchingroom.gif)

3. **Send Friend Requests**
   - Click the Connect button to send connection requests
   - Manage incoming and outgoing requests
![Handle Connect Request Demo](https://github.com/bgkillas/csc207-project/blob/main/assets/connectrequestview.gif)

### **Creating and Sharing Posts**

1. **Create a Post**
   - Navigate to the "Share" section
   - Write about music, concerts, or discoveries
   - Add images if desired
![post](https://github.com/user-attachments/assets/ddc7a008-937f-4ed2-9235-712a0b939d24)

2. **Engage with Posts**
   - Browse posts from other users
   - Add comments and interact with the community
![post](https://github.com/user-attachments/assets/9816b0f3-5f1f-4899-b6b6-032a23ddcd5a)

### **Managing Your Profile**

1. **Update Profile**
   - Access your profile through "My Profile"
   - Update personal information and preferences
![editprofile](https://github.com/user-attachments/assets/abccf630-aae8-44e9-b6ea-d9ab4230d697)


2. **Privacy Settings**
   - Control who can see your profile
   - Manage friend and block lists
![block](https://github.com/user-attachments/assets/66a2d1a2-348b-4b73-8d9d-57250086afd3)

---

## **Architecture Overview**

S-Buddify follows the **Clean Architecture** pattern with clear separation of concerns:

```
src/
├── main/
│   └── java/
│       └── app/
│           ├── entities/                  # Core business logic, independent of external dependencies
│           │   ├── Comment/              
│           │   ├── Match/
│           │   ├── MatchFilter/
│           │   ├── Post/
│           │   ├── User/
│           │   └── UserSession/           
│           ├── usecase/                   # Application-specific business rules
│           │   ├── add_comment/           # Individual use cases organized by features
│           │   ├── add_friend_list/
│           │   ├── create_account/
│           │   ├── create_post/
│           │   └── ...

│           ├── interface_adapter/         # Transform data between use cases and UI
│           │   ├── controller/
│           │   ├── presenter/
│           │   └── viewmodel/
│           ├── frameworks_and_drivers/    # External systems (UI, data access, APIs)
│           │   ├── view/                  # Java Swing GUI components
│           │   ├── data_access/          # In-memory and persistent data access
│           │   └── external/
│           │       └── spotify/          # Spotify API integration
│           └── Main.java                 # Application entry point
│
├── test/
│   └── java/
│       └── app/
│           ├── entity_tests/              # Unit tests for entity classes
│           ├── usecase_tests/             # Unit tests for use case interactors 
│           └── Spotify/                   # Tests for external spotify
```

### **Key Technologies**
- **Java 17**: Programming language
- **Java Swing**: User interface framework
- **Maven**: Build and dependency management
- **JUnit 5**: Testing framework
- **Spotify Web API**: Music data integration
- **JSON**: Data handling

---
## **Feedback**

We welcome constructive feedback to help improve S-Buddify.

1. **How to Give Feedback**
   - Google Form: [Submit Feedback Here – S-Buddify Feedback Form](https://docs.google.com/forms/d/e/1FAIpQLSdGEDqw_VdmkQikZboz-vlOlyf9FIVUM1ipIA10WWyOjcKmJw/viewform?usp=dialog)  

2. What Counts as Valid Feedback
   - Reports of bugs, crashes, or unexpected behaviour
   - Suggestions for new features or improvements
   - Usability feedback (e.g., UI, navigation)
   - Performance issues or API integration problems

3. Guidelines for Feedback
   - Be as specific as possible (steps to reproduce bugs, screenshots, error logs)
   - Include your operating system, Java version, and internet connection type if relevant
   - Be respectful and constructive — personal attacks or inappropriate language will be ignored

4. What to Expect After Submitting Feedback
   - You will receive an acknowledgement within 3 business days
   - Valid bug reports will be logged in our GitHub Issues tracker
   - Feature suggestions will be reviewed in our weekly team meeting and may be added to the roadmap
   - You may be contacted for follow-up questions if clarification is needed

---
## **Contributing**
We welcome contributions from the community! Whether it's fixing bugs, improving documentation, or adding new features, your help makes S-Buddify better.

**How to Contribute**

1. Fork the Repository
   Click the Fork button at the top right of the project repository

2. Clone Your Fork
   ```bash
   git clone https://github.com/your-username/csc207-project.git
   cd csc207-project
   ```
3. Create a New Branch
   ```bash
   git checkout -b feature/your-feature-name
   ```
4. Make Changes
   Follow our code style guidelines (style-check.sh & format-check.sh must pass)
   Write unit tests for new functionality

5. Commit and Push
   ```bash
   git add .
   git commit -m "Add: Description of changes"
   git push origin feature/your-feature-name
   ```
6. Open a Pull Request (PR)
   Go to your fork on GitHub and click New pull request
   Provide a clear description of your changes and why they are needed
   
8. Review & Merge Process
   One team member will review your PR within 5 business days
   Reviewer may request changes — please address them promptly
   Once approved, a maintainer will squash & merge your PR into main
   Larger features may be merged into a staging branch before release

## **License**
This project is licensed under the [MIT License](./LICENSE).  
You are free to use, copy, modify, and distribute this code for academic and personal use, under the terms of the license.






