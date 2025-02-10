> ⚠ **Work in Progress**  
> This project is still under active development. Features may change, and you may encounter unexpected issues. If you are updated from a previous version, you may need to delete your `highscores.db` file and start fresh!
> Please report any bugs or feedback via [GitHub Issues](https://github.com/mikedmor/ArcadeScore/issues).

<p align="center">
  <img src="app/static/images/icons/arcadescore_256.png" />
</p>

ArcadeScore is a self-hosted high-score tracking solution designed for arcade enthusiasts. It enables users to track, display, and manage high scores for their personal or shared arcade setups. The project emphasizes flexibility, user customization, and community engagement.

## 🎮 **Features**

- **High Score Tracking**: Seamlessly log and display high scores for multiple games.
- **Multiple Scoreboards**: Create multiple Scoreboard displays, and access all from a single device.
- **Customizable Scoreboard**: Adjust colors, background images, and styles for your arcade scoreboard.
- **User Authentication**: (Optional) Password-protected admin menu for secure settings management.
- **Auto-Scrolling Scoreboard**: Beautiful, auto-scrolling layout showcasing games and scores.
- **Preset Styles & Custom CSS**: Select from 4 preset styles, or create your own with full CSS customization.
- **Self-Hosted Solution**: Maintain complete control over your data and setup.

## 🖼️ **Preview**

### **ArcadeScore Home Page**
![ArcadeScore Home Page](screenshots/landingPage.png)

<!-- ### **ArcadeScore Scoreboard**
![ArcadeScore Scoreboard](screenshots/scoreboard.png) -->

### **Game Managment**
![Game Managment](screenshots/manageGames.png)

### **Retrieve Game Artwork**
![Retrieve Game Artwork](screenshots/editGame.png)

### **Customize GameCard CSS**
![Game CSS](screenshots/customCSS.png)

### **Custom Style Presets and Preset Management**
![Style Management](screenshots/manageStyles.png)

### **Auto-Scrolling Display Demo**
![Auto-Scrolling Demo](screenshots/Animation.gif)

## 🚀 **Planned Features**

- **Public Tournaments**: Participate in global or regional arcade tournaments.
- **Friend Score Syncing**: Compare high scores with friends in real time.
- **[hi2txt](https://greatstoneex.github.io/hi2txt-doc/) Support**: Arcade Mame Highscores

## 🛠 **Requirements**

Before running ArcadeScore, ensure your system meets the following requirements:

### **🔹 Option 1: Running with Docker**
- **Docker**: [Install Docker](https://www.docker.com/get-started)
- **Docker Compose** (included with newer versions of Docker)

### **🔹 Option 2: Running with Python**
- **Python 3.8+** (Ensure it's installed and added to your system PATH)
- **pip** (Included with Python, but can be updated: `python -m ensurepip --default-pip`)
- **7-Zip** (Required for exports)
  - **Windows**: Automatically installed via `setup.bat` if missing
  - **Linux/macOS**: Installed via `setup.sh` (uses `apt` or `yum`)

#### **💡 Additional Notes**
- **Linux/macOS users** may need `sudo` for dependency installations.
- **Ensure port 8080 is available** if running directly via Python.

## 📥 **Installation Instructions**

1. **Clone the Repository**:
    ```bash
    git clone https://github.com/mikedmor/ArcadeScore.git
    cd ArcadeScore
    ```

2. **Create and update .env file**
    Create a .env file following the .env.sample for assistance. Your file should look something like this
    ```env
    SERVER_NAME="localhost"
    SSL_PEM=selfsigned.info.pem
    SSL_KEY=selfsigned.info.key

    ARCADESCORE_HTTP_PORT=80
    ARCADESCORE_HTTPS_PORT=443
    ```

3. **Run the software**:

    a. **Set Up Docker** (Recommended):
    Ensure Docker is installed and running on your machine. Build and run the container:
    ```bash
    docker-compose up --build -d
    ```

    To stop the software
    ```bash
    docker-compose down
    ```

    b. **Run via Python**:
    If you prefer running ArcadeScore outside of Docker, follow the setup for your system:

    🖥 Windows:
    Run the following in Command Prompt (cmd):
    ```bash
    setup.bat
    ```

    🐧 Linux/macOS:
    Run the following in Terminal:
    ```bash
    ./setup.sh
    ```

4. **Install Certificates** (Optional):
    If you want to remove the browser warnings when utilizing https urls then you will want to install the certificates so that your computer reconizes them as a "Trusted Root Certification Authority". Follow these steps to do that.

    - In the certs folder find the `selfsigned.info.crt`
    - right click on this file and select "Install Certificate" (Windows)
    - select "Local Machine" then click Next, allow UAC
    - select "Place all certificates in the following store", then press the browse button
    - Select "Trusted Root Certification Authorities", then press Ok
    - Press Next, then Finish to install the certificate
    - Done, you should now be able to access https://localhost and see the application without a warning

    Note: These steps utilize the included self-signed certificates. If you want more security then it is recommended that you generate your own using OpenSSL
    ```bash
    openssl req -x509 -newkey rsa:4096 -keyout cert.key -out cert.crt -days 365 -nodes -subj "/CN=localhost" && \
      openssl x509 -outform der -in cert.crt -out cert.der && \
      cat cert.key cert.crt > cert.pem
    ```

5. **Access the Application**:
  - Open your browser and navigate to **`https://localhost`**. You should see the landing page.
  - Click the scoreboard to access the **default scoreboard**, or create a new one

6. **Default Setup**:
    The default settings create a sample scoreboard. Customize settings via the admin menu on the scoreboard!

## 🤝 **Contributing**

We welcome contributions from the community! If you’d like to help:

1. **Fork** the repository on GitHub.
2. **Create a new branch** for your feature or bug fix.
3. **Submit a pull request (PR)** with detailed information about your changes.
4. Engage in discussions and improvements in the **Issues** section.

Your contributions make **ArcadeScore** better for everyone!

## ☕ **Donate** 

ArcadeScore is a free, open-source project designed to provide a self-hosted high-score tracking solution for virtual pinball and arcade setups. If you enjoy using ArcadeScore and would like to support its continued development, consider buying me a coffee! 

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/mikedmor)

Your support helps keep this project alive and improving. Thank you!  

## 🎯 **Goals**

The vision for **ArcadeScore** is to:
- Provide a **robust, open-source** solution for arcade score tracking.
- Foster a **community-driven** approach where users contribute and improve the platform.
- Offer **flexible deployment** options suitable for hobbyists and professional arcade setups.

## 📊 **Progress**

- [ ] Core features
  - [x] **VPin Studio Integration** (via iScored)
    - [x] Table Subscriptions
    - [x] Pulling High Scores
    - [x] Submitting New Scores
  - [ ] **VPin Studio 'API' Integration**
    - [x] Create Scoreboard with integration
    - [ ] Auto Register for updates (via Webhooks)
    - [x] Import Games
    - [x] Import Game Media
      - [x] Capture image from mp4 frame
      - [x] Auto rotate playfield for background
    - [ ] Import/Update Players
      - [x] Wizard
      - [ ] Scoreboard
    - [ ] Import Scores
      - [x] Wizard
      - [ ] Scoreboard
  - [ ] **Game Management**
    - [x] Game List
    - [x] Hide Games
    - [x] Edit Games
    - [x] Delete Games
    - [x] Add Games
    - [x] Load Details from VPS
    - [x] Score Display Options
    - [ ] Reverse Sort
    - [x] Custom CSS
    - [x] Preset CSS Templates
    - [x] Copy CSS Between Games
  - [ ] **Player Management**
    - [x] Player List
    - [ ] Hide Player
    - [ ] Edit Player
    - [ ] Delete Player
    - [x] Add Player
    - [x] Map multiple initials to a single player
  - [ ] **Style Management**
    - [x] Copy Style to All Games
    - [x] Custom CSS Styles
    - [x] Preset CSS Styles
      - [ ] 4 Included Styles
        - [x] Default
        - [ ] ?????
        - [ ] ?????
        - [ ] ?????
    - [ ] Font Installer
  - [ ] **Admin Settings**
    - [ ] Room Name Customization
    - [ ] Date Format Selection
    - [ ] Enable/Disable Manual Score Input
    - [ ] Auto Refresh Toggle
    - [ ] Disable Fullscreen Trigger
    - [ ] Idle Scroll Toggle & Speed
    - [ ] Long Names Enabled
    - [ ] Password Protection
  - [x] **Sockets for Realtime updates**
    - [x] Create Scoreboard VPin Studio Import Progress Socket
    - [x] Score Update Socket
    - [x] Scoreboard change socket
      -[x] Game Adjustments/Changes
      -[x] Game Style Adjustments/Changes
      -[x] Global Style Adjustments/Changes
      -[x] Player Adjustments/Changes
- [ ] **Deployment Options**
  - [x] Windows Deployment
  - [x] Linux Deployment
  - [ ] Mac Deployment
  - [x] **Dockerized Deployment**
- [x] **Multiple Scoreboards**
- [x] **Improved Landing Page**
- [x] **Mobile Support**
- [x] **Import/Export database and media**
- [ ] **[hi2txt](https://greatstoneex.github.io/hi2txt-doc/) MAME Support** *(Looking for assistance!)*
- [ ] **Performance Improvements**
- [ ] **Tournaments**
  - [ ] Private Tournament Bracket
  - [ ] Public Tournament Bracket (SYNC)
- [ ] **Sync with Friends (SYNC)**

## 🐞 **Known Bugs**
- Vertical score scrolling does not work on mobile
- Drag game reordering is slow when dragging down the list
- New Player alias default changes when adding new aliases
- Most setting adjustments do not actually work currently
- Images from VPIN-Spreadsheet are uncompressed
- Games Menu drag and drop loses shadow placement after first change (refresh fixes it)
- Apply to All Games is very slow with large number of games

## 📜 **License**

**ArcadeScore** is released under the **[MIT License](LICENSE)**.

---

For support or inquiries, please visit the GitHub repository's [Issues](https://github.com/yourusername/Arcadescore/issues) section.
