#!/usr/bin/env python3
"""
Overcast Agent GUI Installer
====================================

Windows-compatible GUI installer using Python + Tkinter that walks users through
installing the Overcast Agent into their application project.

Features:
- 5-step guided installation process
- Auto-detection of deployment platforms
- Dockerfile modification/creation
- Project integration with .env configuration
- Platform-specific deployment instructions

Requirements: Python 3.9+ with Tkinter (standard library)
"""

import os
import sys
import json
import re
import shutil
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path
import threading
import platform
from typing import Optional, Dict, Any


class OvercastInstaller:
    """Main installer application class"""
    
    def __init__(self):
        self.root = tk.Tk()
        # Set title with platform indicator
        platform_name = platform.system()
        self.root.title(f"Overcast Agent Installer ({platform_name})")
        self.root.geometry("600x500")
        self.root.resizable(False, False)
        
        # Apply dark theme colors
        self.root.configure(bg='#0d1117')
        
        # Configure ttk styles for dark theme
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        # Configure dark theme colors
        self.style.configure('TFrame', background='#0d1117')
        self.style.configure('TLabel', background='#0d1117', foreground='#e6edf3', font=('SF Mono', 10))
        self.style.configure('Title.TLabel', background='#0d1117', foreground='#e6edf3', font=('SF Mono', 16, 'bold'))
        self.style.configure('TButton', background='#21262d', foreground='#e6edf3', borderwidth=1, relief='solid')
        self.style.map('TButton', 
                      background=[('active', '#30363d'), ('pressed', '#58a6ff')],
                      foreground=[('active', '#e6edf3')])
        self.style.configure('TEntry', fieldbackground='#161b22', foreground='#e6edf3', borderwidth=1, 
                           insertcolor='#e6edf3', selectbackground='#58a6ff')
        self.style.configure('TProgressbar', background='#58a6ff', troughcolor='#21262d', borderwidth=0)
        
        # Application state
        self.current_step = 0
        self.api_key = ""
        self.project_path = ""
        self.deployment_type = ""
        
        # UI components
        self.setup_ui()
        
        # Platform detection
        self.platform_info = self._detect_platform()
        
        # Start with step 1
        self.show_step(0)
    
    def setup_ui(self):
        """Setup the main UI structure"""
        # Main container
        self.main_frame = ttk.Frame(self.root, padding="20")
        self.main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        self.main_frame.columnconfigure(0, weight=1)
        
        # Title
        self.title_label = ttk.Label(
            self.main_frame, 
            text="🚀 Overcast Agent Installer",
            style="Title.TLabel"
        )
        self.title_label.grid(row=0, column=0, pady=(0, 20))
        
        # Progress bar
        self.progress_frame = ttk.Frame(self.main_frame)
        self.progress_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 20))
        self.progress_frame.columnconfigure(0, weight=1)
        
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            self.progress_frame, 
            variable=self.progress_var, 
            maximum=5
        )
        self.progress_bar.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
        self.progress_label = ttk.Label(
            self.progress_frame, 
            text="Step 1 of 5"
        )
        self.progress_label.grid(row=1, column=0, pady=(5, 0))
        
        # Content frame (will be replaced for each step)
        self.content_frame = ttk.Frame(self.main_frame)
        self.content_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 20))
        self.content_frame.columnconfigure(0, weight=1)
        self.main_frame.rowconfigure(2, weight=1)
        
        # Button frame
        self.button_frame = ttk.Frame(self.main_frame)
        self.button_frame.grid(row=3, column=0, sticky=(tk.W, tk.E))
        
        self.back_button = ttk.Button(
            self.button_frame, 
            text="← Back", 
            command=self.go_back,
            state="disabled"
        )
        self.back_button.grid(row=0, column=0, padx=(0, 10))
        
        self.next_button = ttk.Button(
            self.button_frame, 
            text="Next →", 
            command=self.go_next
        )
        self.next_button.grid(row=0, column=2)
        
        # Add spacing column
        self.button_frame.columnconfigure(1, weight=1)
    
    def show_step(self, step_num: int):
        """Show the specified step"""
        self.current_step = step_num
        self.progress_var.set(step_num + 1)
        self.progress_label.config(text=f"Step {step_num + 1} of 5")
        
        # Clear content frame
        for widget in self.content_frame.winfo_children():
            widget.destroy()
        
        # Show appropriate step
        if step_num == 0:
            self.show_api_key_step()
        elif step_num == 1:
            self.show_project_selection_step()
        elif step_num == 2:
            self.show_deployment_detection_step()
        elif step_num == 3:
            self.show_installation_step()
        elif step_num == 4:
            self.show_completion_step()
        
        # Update button states
        self.back_button.config(state="normal" if step_num > 0 else "disabled")
        if step_num == 4:
            self.next_button.config(text="Finish", command=self.finish_installation)
        else:
            self.next_button.config(text="Next →", command=self.go_next)
    
    def show_api_key_step(self):
        """Step 1: API Key Input"""
        header_label = ttk.Label(
            self.content_frame,
            text="🔑 Enter your Overcast API Key"
        )
        self.style.configure('Header.TLabel', background='#0d1117', foreground='#e6edf3', font=('SF Mono', 12, 'bold'))
        header_label.configure(style='Header.TLabel')
        header_label.grid(row=0, column=0, pady=(0, 10))
        
        ttk.Label(
            self.content_frame,
            text="You can get your API key from the Overcast dashboard:",
            wraplength=500
        ).grid(row=1, column=0, pady=(0, 5))
        
        # API key input
        self.api_key_var = tk.StringVar(value=self.api_key)
        api_key_entry = ttk.Entry(
            self.content_frame,
            textvariable=self.api_key_var,
            width=50,
            show="*"
        )
        api_key_entry.grid(row=2, column=0, pady=(10, 10))
        api_key_entry.focus()
        
        # Help text
        help_text = """
ℹ️  Your API key is used to securely connect your application 
logs to the Overcast monitoring dashboard.

Your customer account will be automatically identified from your API key.
        """
        
        help_label = ttk.Label(
            self.content_frame,
            text=help_text.strip(),
            wraplength=500,
            justify="left"
        )
        self.style.configure('Help.TLabel', background='#0d1117', foreground='#8b949e', font=('SF Mono', 9))
        help_label.configure(style='Help.TLabel')
        help_label.grid(row=3, column=0, pady=(20, 0))
    
    def show_project_selection_step(self):
        """Step 2: Project Directory Selection"""
        ttk.Label(
            self.content_frame,
            text="📁 Select Your Project Directory",
            font=("Arial", 12, "bold")
        ).grid(row=0, column=0, pady=(0, 10))
        
        ttk.Label(
            self.content_frame,
            text="Choose the root directory of your application project:",
            wraplength=500
        ).grid(row=1, column=0, pady=(0, 20))
        
        # Directory selection frame
        dir_frame = ttk.Frame(self.content_frame)
        dir_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 20))
        dir_frame.columnconfigure(0, weight=1)
        
        self.project_path_var = tk.StringVar(value=self.project_path)
        path_entry = ttk.Entry(
            dir_frame,
            textvariable=self.project_path_var,
            width=60,
            state="readonly"
        )
        path_entry.grid(row=0, column=0, padx=(0, 10))
        
        browse_button = ttk.Button(
            dir_frame,
            text="Browse...",
            command=self.browse_project_directory
        )
        browse_button.grid(row=0, column=1)
        
        # Help text
        help_text = """
ℹ️  Select the root directory of your application project.
This should contain your main application files (app.py, main.py, etc.)
and may contain a Dockerfile, requirements.txt, or platform config files.

We'll automatically detect your deployment platform and integrate
the overcast agent accordingly.
        """
        
        help_label2 = ttk.Label(
            self.content_frame,
            text=help_text.strip(),
            wraplength=500,
            justify="left"
        )
        help_label2.configure(style='Help.TLabel')
        help_label2.grid(row=3, column=0, pady=(20, 0))
    
    def show_deployment_detection_step(self):
        """Step 3: Deployment Type Detection"""
        ttk.Label(
            self.content_frame,
            text="🔍 Deployment Platform Detection",
            font=("Arial", 12, "bold")
        ).grid(row=0, column=0, pady=(0, 10))
        
        # Run detection
        self.deployment_type = self.detect_deployment_type()
        
        # Show results
        result_frame = ttk.LabelFrame(self.content_frame, text="Detection Results", padding="15")
        self.style.configure('TLabelframe', background='#0d1117', borderwidth=1, relief='solid')
        self.style.configure('TLabelframe.Label', background='#0d1117', foreground='#58a6ff', font=('SF Mono', 10, 'bold'))
        result_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(10, 20))
        result_frame.columnconfigure(0, weight=1)
        
        platform_text = f"🎯 Detected Platform: {self.deployment_type}"
        ttk.Label(
            result_frame,
            text=platform_text,
            font=("Arial", 11, "bold")
        ).grid(row=0, column=0, pady=(0, 10))
        
        # Show what was found
        detection_details = self.get_detection_details()
        ttk.Label(
            result_frame,
            text=detection_details,
            wraplength=500,
            justify="left"
        ).grid(row=1, column=0)
        
        # Installation preview
        preview_frame = ttk.LabelFrame(self.content_frame, text="Installation Preview", padding="15")
        preview_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 20))
        preview_frame.columnconfigure(0, weight=1)
        
        preview_text = self.get_installation_preview()
        ttk.Label(
            preview_frame,
            text=preview_text,
            wraplength=250,
            justify="left"
        ).grid(row=0, column=0)
    
    def show_installation_step(self):
        """Step 4: Perform Installation"""
        ttk.Label(
            self.content_frame,
            text="⚙️ Installing Overcast Agent",
            font=("Arial", 12, "bold")
        ).grid(row=0, column=0, pady=(0, 20))
        
        # Progress text widget
        self.install_text = tk.Text(
            self.content_frame,
            height=15,
            width=70,
            wrap=tk.WORD,
            font=("SF Mono", 9),
            bg='#161b22',
            fg='#e6edf3',
            insertbackground='#e6edf3',
            selectbackground='#58a6ff',
            selectforeground='#ffffff',
            relief='solid',
            borderwidth=1
        )
        self.install_text.grid(row=1, column=0, pady=(0, 20))
        
        # Scrollbar for text widget
        scrollbar = ttk.Scrollbar(self.content_frame, orient="vertical", command=self.install_text.yview)
        scrollbar.grid(row=1, column=1, sticky=(tk.N, tk.S))
        self.install_text.configure(yscrollcommand=scrollbar.set)
        
        # Disable next button during installation
        self.next_button.config(state="disabled")
        
        # Start installation in a separate thread
        threading.Thread(target=self.perform_installation, daemon=True).start()
    
    def show_completion_step(self):
        """Step 5: Show completion and deployment instructions"""
        success_label = ttk.Label(
            self.content_frame,
            text="🎉 Installation Complete!"
        )
        self.style.configure('Success.TLabel', background='#0d1117', foreground='#238636', font=('SF Mono', 14, 'bold'))
        success_label.configure(style='Success.TLabel')
        success_label.grid(row=0, column=0, pady=(0, 20))
        
        # Success message
        ttk.Label(
            self.content_frame,
            text="The Overcast Agent has been successfully installed into your project.",
            wraplength=500,
            justify="center"
        ).grid(row=1, column=0, pady=(0, 20))
        
        # Deployment instructions
        instructions_frame = ttk.LabelFrame(self.content_frame, text="Next Steps", padding="15")
        instructions_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 20))
        instructions_frame.columnconfigure(0, weight=1)
        
        instructions = self.get_deployment_instructions()
        ttk.Label(
            instructions_frame,
            text=instructions,
            wraplength=500,
            justify="left"
        ).grid(row=0, column=0)
        
        # Dashboard link
        dashboard_frame = ttk.LabelFrame(self.content_frame, text="Dashboard Access", padding="15")
        dashboard_frame.grid(row=3, column=0, sticky=(tk.W, tk.E))
        dashboard_frame.columnconfigure(0, weight=1)
        
        ttk.Label(
            dashboard_frame,
            text="🌐 Access your Overcast dashboard at:",
            font=("Arial", 10, "bold")
        ).grid(row=0, column=0, pady=(0, 5))
        
        dashboard_url = "https://dashboard.overcastsre.com"
        dashboard_link = ttk.Label(
            dashboard_frame,
            text=dashboard_url,
            foreground="blue",
            cursor="hand2"
        )
        dashboard_link.grid(row=1, column=0)
        dashboard_link.bind("<Button-1>", lambda e: self.open_url(dashboard_url))
    
    def browse_project_directory(self):
        """Open directory browser for project selection"""
        directory = filedialog.askdirectory(
            title="Select Project Directory",
            initialdir=os.getcwd()
        )
        
        if directory:
            self.project_path = directory
            self.project_path_var.set(directory)
    
    def detect_deployment_type(self) -> str:
        """Auto-detect deployment platform based on project files"""
        if not self.project_path:
            return "Unknown"
        
        project_dir = Path(self.project_path)
        
        # Check for Railway
        if (project_dir / "railway.json").exists():
            return "Railway"
        
        # Check for Heroku
        if (project_dir / "Procfile").exists():
            return "Heroku"
        
        # Check for GCP App Engine
        if (project_dir / "app.yaml").exists() or (project_dir / ".gcloudignore").exists():
            return "Google Cloud Platform"
        
        # Check for AWS
        if (project_dir / ".ebextensions").exists() or (project_dir / "Dockerrun.aws.json").exists():
            return "AWS"
        
        # Check for Azure
        if (project_dir / "azure-pipelines.yml").exists():
            return "Microsoft Azure"
        
        # Check for GitHub Actions with cloud deployment
        github_dir = project_dir / ".github" / "workflows"
        if github_dir.exists():
            for workflow_file in github_dir.glob("*.yml"):
                content = workflow_file.read_text().lower()
                if any(cloud in content for cloud in ["aws", "gcp", "azure", "railway", "heroku"]):
                    return "GitHub Actions + Cloud"
        
        # Check for Docker
        if (project_dir / "Dockerfile").exists():
            return "Docker (Custom)"
        
        return "Custom/Local"
    
    def get_detection_details(self) -> str:
        """Get detailed information about what was detected"""
        if not self.project_path:
            return "No project directory selected."
        
        project_dir = Path(self.project_path)
        details = []
        
        # Check specific files found
        files_found = []
        check_files = [
            ("railway.json", "Railway configuration"),
            ("Procfile", "Heroku process file"),
            ("app.yaml", "GCP App Engine config"),
            ("Dockerfile", "Docker container config"),
            ("requirements.txt", "Python dependencies"),
            ("package.json", "Node.js dependencies")
        ]
        
        for filename, description in check_files:
            if (project_dir / filename).exists():
                files_found.append(f"✅ {description} ({filename})")
        
        if files_found:
            details.append("📄 Configuration files found:")
            details.extend(files_found)
        else:
            details.append("📄 No specific deployment configuration files found.")
        
        return "\n".join(details)
    
    def get_installation_preview(self) -> str:
        """Get preview of what will be installed"""
        actions = [
            "📄 Copy overcast_agent.py to project root",
            "📁 Create logs/ directory if missing",
            "🔧 Create/update .env file with API key",
        ]
        
        if Path(self.project_path) / "Dockerfile" if self.project_path else False:
            actions.append("🐳 Modify existing Dockerfile to run overcast agent")
        else:
            actions.append("ℹ️  No Dockerfile found - Docker integration will be skipped")
        
        actions.append("✅ Configure log streaming to Overcast dashboard")
        
        return "\n".join(actions)
    
    def perform_installation(self):
        """Perform the actual installation"""
        try:
            self.log_install("🚀 Starting Overcast Agent installation...\n")
            
            # Step 1: Copy overcast_agent.py
            self.log_install("📄 Copying overcast_agent.py...")
            self.copy_log_forwarder()
            self.log_install("✅ Log forwarder copied successfully\n")
            
            # Step 2: Create logs directory
            self.log_install("📁 Creating logs directory...")
            self.create_logs_directory()
            self.log_install("✅ Logs directory created\n")
            
            # Step 3: Create/update .env file
            self.log_install("🔧 Configuring environment variables...")
            self.create_env_file()
            self.log_install("✅ Environment configuration updated\n")
            
            # Step 4: Handle Dockerfile
            self.log_install("🐳 Configuring Docker integration...")
            self.handle_dockerfile()
            self.log_install("✅ Docker configuration complete\n")
            
            # Step 5: Create requirements.txt if needed
            self.log_install("📦 Checking Python dependencies...")
            self.handle_requirements()
            self.log_install("✅ Dependencies configured\n")
            
            self.log_install("🎉 Installation completed successfully!")
            self.log_install("\n✨ Your project is now ready for deployment with Overcast monitoring!")
            
            # Enable next button
            self.root.after(0, lambda: self.next_button.config(state="normal"))
            
        except Exception as e:
            self.log_install(f"\n❌ Installation failed: {str(e)}")
            self.root.after(0, lambda: messagebox.showerror("Installation Error", f"Installation failed: {str(e)}"))
            self.root.after(0, lambda: self.next_button.config(state="normal"))
    
    def log_install(self, message: str):
        """Log installation progress to the text widget"""
        def update_text():
            self.install_text.insert(tk.END, message + "\n")
            self.install_text.see(tk.END)
            self.install_text.update()
        
        self.root.after(0, update_text)
    
    def copy_log_forwarder(self):
        """Copy the overcast agent template to the project"""
        template_path = Path(__file__).parent / "overcast_agent_template.py"
        target_path = Path(self.project_path) / "overcast_agent.py"
        
        if not template_path.exists():
            raise FileNotFoundError("overcast_agent_template.py not found in installer directory")
        
        shutil.copy2(template_path, target_path)
    
    def create_logs_directory(self):
        """Create logs directory if it doesn't exist"""
        logs_dir = Path(self.project_path) / "logs"
        logs_dir.mkdir(exist_ok=True)
        
        # Create a .gitkeep file
        gitkeep_file = logs_dir / ".gitkeep"
        gitkeep_file.touch()
    
    def create_env_file(self):
        """Create or update .env file with configuration"""
        env_path = Path(self.project_path) / ".env"
        
        # Read existing .env if it exists
        existing_vars = {}
        if env_path.exists():
            with open(env_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        existing_vars[key.strip()] = value.strip()
        
        # Set/update Overcast variables  
        existing_vars['OVERCAST_API_KEY'] = self.api_key_var.get().strip()
        existing_vars['OVERCAST_DASHBOARD_URL'] = 'https://dashboard.overcastsre.com'
        existing_vars['OVERCAST_LOG_FILE'] = '/app.log'
        
        # Write updated .env file
        with open(env_path, 'w') as f:
            f.write("# Overcast Agent Configuration\n")
            for key, value in existing_vars.items():
                f.write(f"{key}={value}\n")
    
    def handle_dockerfile(self):
        """Modify existing Dockerfile to integrate overcast agent"""
        dockerfile_path = Path(self.project_path) / "Dockerfile"
        
        if dockerfile_path.exists():
            self.modify_existing_dockerfile(dockerfile_path)
        else:
            self.log_install("ℹ️  No Dockerfile found - skipping Docker integration")
            self.log_install("💡 Contact support for help with Docker setup")
    
    def modify_existing_dockerfile(self, dockerfile_path: Path):
        """Modify existing Dockerfile to run overcast agent"""
        with open(dockerfile_path, 'r') as f:
            content = f.read()
        
        # Check if already modified
        if 'overcast_agent.py' in content:
            self.log_install("ℹ️  Dockerfile already contains overcast agent integration")
            return
        
        # Find the CMD or ENTRYPOINT line and modify it
        lines = content.split('\n')
        modified = False
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith('CMD') or stripped.startswith('ENTRYPOINT'):
                # Extract the command
                if stripped.startswith('CMD'):
                    # Replace with platform-appropriate command format
                    new_cmd = self._get_platform_docker_cmd()
                    lines[i] = new_cmd
                    modified = True
                    break
        
        if not modified:
            # Add our own CMD if none found
            lines.append('')
            lines.append('# Overcast Agent Integration')
            lines.append(self._get_platform_docker_cmd())
        
        # Write modified Dockerfile
        with open(dockerfile_path, 'w') as f:
            f.write('\n'.join(lines))
    

    
    def handle_requirements(self):
        """Ensure required packages are in requirements.txt"""
        requirements_path = Path(self.project_path) / "requirements.txt"
        
        required_packages = [
            'psutil',
            'requests',
            'python-dotenv'
        ]
        
        existing_requirements = set()
        if requirements_path.exists():
            with open(requirements_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        # Extract package name (before any version specifier)
                        package_name = re.split(r'[>=<~!]', line)[0].strip()
                        existing_requirements.add(package_name.lower())
        
        # Add missing packages
        missing_packages = []
        for package in required_packages:
            if package.lower() not in existing_requirements:
                missing_packages.append(package)
        
        if missing_packages:
            with open(requirements_path, 'a') as f:
                f.write('\n# Overcast Agent Dependencies\n')
                requirements_text = self._get_platform_specific_requirements()
                for line in requirements_text.split('\n'):
                    if line.strip() in missing_packages:
                        f.write(f'{line.strip()}\n')
            
            self.log_install(f"📦 Added dependencies: {', '.join(missing_packages)}")
        else:
            self.log_install("📦 All required dependencies already present")
    
    def get_deployment_instructions(self) -> str:
        """Get platform-specific deployment instructions"""
        git_commands = self._get_platform_git_commands()
        
        instructions = {
            "Railway": f"""
1. 🚂 Commit your changes:
   {git_commands['add']}
   {git_commands['commit']}

2. 🚀 Push to Railway:
   {git_commands['push']}

3. ✅ Your app will redeploy automatically with log monitoring enabled!
            """.strip(),
            
            "Heroku": """
1. 🟣 Commit your changes:
   git add .
   git commit -m "Add Overcast overcast agent"

2. 🚀 Deploy to Heroku:
   git push heroku main

3. ✅ Your dyno will restart with log monitoring enabled!
            """.strip(),
            
            "Google Cloud Platform": """
1. ☁️ Deploy to GCP:
   gcloud app deploy

2. ✅ Your app will redeploy with log monitoring enabled!
            """.strip(),
            
            "AWS": """
1. ☁️ Rebuild and deploy your Docker container:
   docker build -t your-app .
   # Deploy using your AWS deployment method

2. ✅ Your application will restart with log monitoring enabled!
            """.strip(),
            
            "Docker (Custom)": """
1. 🐳 Rebuild your Docker container:
   docker build -t your-app .

2. 🚀 Run with environment variables:
   docker run --env-file .env your-app

3. ✅ Your application will start with log monitoring enabled!
            """.strip(),
            
            "Custom/Local": f"""
1. 📦 Install dependencies:
   {self.platform_info['python_cmd']} -m pip install -r requirements.txt

2. 🚀 Run your application:
   {self.platform_info['python_cmd']} app.py > /app.log 2>&1 &
   {self.platform_info['python_cmd']} overcast_agent.py

3. ✅ Your application logs will be forwarded to Overcast!
            """.strip()
        }
        
        return instructions.get(self.deployment_type, instructions["Custom/Local"])
    
    def go_next(self):
        """Move to next step with validation"""
        if self.current_step == 0:
            # Validate API key
            api_key = self.api_key_var.get().strip()
            if not api_key:
                messagebox.showerror("Validation Error", "Please enter your Overcast API key.")
                return
            
            self.api_key = api_key
        
        elif self.current_step == 1:
            # Validate project path
            if not self.project_path:
                messagebox.showerror("Validation Error", "Please select your project directory.")
                return
            
            if not os.path.exists(self.project_path):
                messagebox.showerror("Validation Error", "Selected directory does not exist.")
                return
        
        # Move to next step
        if self.current_step < 4:
            self.show_step(self.current_step + 1)
    
    def go_back(self):
        """Move to previous step"""
        if self.current_step > 0:
            self.show_step(self.current_step - 1)
    
    def finish_installation(self):
        """Finish the installation and close the app"""
        messagebox.showinfo(
            "Installation Complete",
            "Overcast Agent has been successfully installed!\n\n"
            "Follow the deployment instructions to activate monitoring for your application."
        )
        self.root.quit()
    
    def open_url(self, url: str):
        """Open URL in default browser"""
        import webbrowser
        webbrowser.open(url)
    
    def _detect_platform(self) -> Dict[str, Any]:
        """Detect the current platform and return platform-specific info"""
        system = platform.system().lower()
        
        platform_info = {
            'system': system,
            'is_windows': system == 'windows',
            'is_linux': system == 'linux', 
            'is_mac': system == 'darwin',
            'python_cmd': 'python',
            'shell_cmd': 'bash' if system != 'windows' else 'cmd'
        }
        
        # Determine best Python command
        if not platform_info['is_windows']:
            # On Linux/Mac, prefer python3
            try:
                import subprocess
                result = subprocess.run(['python3', '--version'], 
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    platform_info['python_cmd'] = 'python3'
            except:
                pass
        
        return platform_info
    
    def _get_platform_specific_requirements(self) -> str:
        """Get platform-specific requirements text"""
        if self.platform_info['is_windows']:
            return "psutil\nrequests\npython-dotenv"
        else:
            # Linux/Mac might need different package names
            return "psutil\nrequests\npython-dotenv"
    
    def _get_platform_docker_cmd(self) -> str:
        """Get platform-appropriate Docker CMD format"""
        # All platforms use the same Docker CMD format
        return 'CMD ["sh", "-c", "python app.py > /app.log 2>&1 & sleep 5 && python overcast_agent.py"]'
    
    def _get_platform_git_commands(self) -> Dict[str, str]:
        """Get platform-appropriate git commands"""
        return {
            'add': 'git add .',
            'commit': 'git commit -m "Add Overcast agent"',
            'push': 'git push origin main'
        }
    
    def run(self):
        """Run the installer application"""
        try:
            # Center the window
            self.root.update_idletasks()
            x = (self.root.winfo_screenwidth() - self.root.winfo_width()) // 2
            y = (self.root.winfo_screenheight() - self.root.winfo_height()) // 2
            self.root.geometry(f"+{x}+{y}")
            
            # Start the main loop
            self.root.mainloop()
        
        except KeyboardInterrupt:
            print("Installation cancelled by user.")
        except Exception as e:
            messagebox.showerror("Application Error", f"An error occurred: {str(e)}")


def main():
    """Main entry point"""
    platform_name = platform.system()
    print(f"🚀 Starting Overcast Agent Installer ({platform_name})...")
    
    # Check Python version
    if sys.version_info < (3, 9):
        print("❌ Python 3.9 or higher is required!")
        if platform.system() == "Windows":
            input("Press Enter to exit...")
        else:
            input("Press Enter to exit...")
        sys.exit(1)
    
    # Show platform-specific compatibility info
    if platform.system() == "Windows":
        print("🪟 Windows detected - using Windows-compatible features")
    elif platform.system() == "Linux": 
        print("🐧 Linux detected - using cross-platform features")
    elif platform.system() == "Darwin":
        print("🍎 macOS detected - using cross-platform features")
    
    try:
        # Create and run installer
        installer = OvercastInstaller()
        installer.run()
        
    except ImportError as e:
        if 'tkinter' in str(e):
            print("❌ Tkinter is not available. Please install Python with tkinter support.")
            print("On some Linux systems: sudo apt-get install python3-tk")
        else:
            print(f"❌ Missing dependency: {e}")
        input("Press Enter to exit...")
        sys.exit(1)
    
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        input("Press Enter to exit...")
        sys.exit(1)


if __name__ == "__main__":
    main() 