#!/usr/bin/env python3
"""
Human Augmented Analytics Group -  Progress Bot

A sophisticated bot that tracks multiple research projects and sends
beautifully formatted progress updates using Slack's Blocks API.
"""

import os
import json
import time
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

# Load environment variables from .env file if it exists
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # dotenv not installed, skip loading .env file
    pass


@dataclass
class ProjectConfig:
    """Configuration for a single project."""
    name: str
    repo_owner: str
    repo_name: str
    milestone_number: int
    emoji: str = "📊"
    color: str = "#36a64f"  # Green


class ProgressBot:
    """ Slack bot for multi-project progress tracking."""
    
    def __init__(self, slack_token: str, github_token: str, user_id: str):
        """
        Initialize the  progress bot.
        
        Args:
            slack_token: Slack bot OAuth token
            github_token: GitHub personal access token
            user_id: Slack user ID to send updates to
        """
        self.slack_token = slack_token
        self.github_token = github_token
        self.user_id = user_id
        
        self.slack_headers = {
            'Authorization': f'Bearer {slack_token}',
            'Content-Type': 'application/json'
        }
        
        self.github_headers = {
            'Authorization': f'token {github_token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        # Repository configuration
        self.repo_owner = "leyangloh"
        self.repo_name = "FakeProgress"
        
        # Milestones will be auto-discovered from GitHub
        self.milestones = []
    
    def discover_all_milestones(self) -> List[ProjectConfig]:
        """
        Auto-discover all milestones in the repository.
        
        Returns:
            List of ProjectConfig objects for all milestones
        """
        url = f'https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/milestones'
        
        try:
            response = requests.get(url, headers=self.github_headers, params={'state': 'all'})
            response.raise_for_status()
            
            milestones = response.json()
            discovered_milestones = []
            
            # Emoji mapping for different milestone types
            emoji_map = {
                0: "🚀",  # First milestone
                1: "🔬",  # Research/testing
                2: "📊",  # Analysis/data
                3: "🎯",  # Goals/targets
                4: "🏆",  # Achievements
                5: "⭐",  # Features
            }
            
            for i, milestone in enumerate(milestones):
                # Get appropriate emoji
                emoji = emoji_map.get(i % len(emoji_map), "📋")
                
                # Assign colors based on state
                if milestone['state'] == 'closed':
                    color = "#28a745"  # Green for completed
                elif milestone['open_issues'] == 0:
                    color = "#ffc107"  # Yellow for no issues
                else:
                    color = "#007bff"  # Blue for active
                
                config = ProjectConfig(
                    name=milestone['title'],
                    repo_owner=self.repo_owner,
                    repo_name=self.repo_name,
                    milestone_number=milestone['number'],
                    emoji=emoji,
                    color=color
                )
                discovered_milestones.append(config)
            
            print(f"🔍 Discovered {len(discovered_milestones)} milestones in {self.repo_owner}/{self.repo_name}")
            return discovered_milestones
            
        except requests.RequestException as e:
            print(f"❌ Error discovering milestones: {e}")
            return []

    def get_milestone_data(self, project: ProjectConfig) -> Optional[Dict[str, Any]]:
        """
        Fetch milestone data from GitHub API.
        
        Args:
            project: Project configuration
            
        Returns:
            Milestone data dictionary or None if failed
        """
        url = f'https://api.github.com/repos/{project.repo_owner}/{project.repo_name}/milestones/{project.milestone_number}'
        
        try:
            response = requests.get(url, headers=self.github_headers)
            response.raise_for_status()
            
            milestone = response.json()
            
            total_issues = milestone['open_issues'] + milestone['closed_issues']
            closed_issues = milestone['closed_issues']
            progress_percentage = (closed_issues / total_issues * 100) if total_issues > 0 else 0
            
            return {
                'title': milestone['title'],
                'description': milestone.get('description', ''),
                'total_issues': total_issues,
                'closed_issues': closed_issues,
                'open_issues': milestone['open_issues'],
                'progress_percentage': progress_percentage,
                'due_date': milestone.get('due_on'),
                'html_url': milestone['html_url'],
                'created_at': milestone['created_at'],
                'updated_at': milestone['updated_at'],
                'state': milestone['state']
            }
            
        except requests.RequestException as e:
            print(f"❌ Error fetching milestone data for {project.name}: {e}")
            return None
    
    def create_progress_bar(self, percentage: float, width: int = 20) -> str:
        """
        Create a visual progress bar using Unicode characters.
        
        Args:
            percentage: Progress percentage (0-100)
            width: Width of the progress bar in characters
            
        Returns:
            Unicode progress bar string
        """
        filled = int(percentage / 100 * width)
        empty = width - filled
        
        # Using block characters for better visual appeal
        filled_char = "█"
        empty_char = "░"
        
        return f"{filled_char * filled}{empty_char * empty}"
    
    def get_status_emoji(self, percentage: float) -> str:
        """Get status emoji based on progress percentage."""
        if percentage >= 100:
            return "✅"
        elif percentage >= 75:
            return "🟢"
        elif percentage >= 50:
            return "🟡"
        elif percentage >= 25:
            return "🟠"
        else:
            return "🔴"
    
    def get_trend_indicator(self, current: float, previous: float = None) -> str:
        """Get trend indicator emoji."""
        if previous is None:
            return "📊"
        
        if current > previous:
            return "📈"
        elif current < previous:
            return "📉"
        else:
            return "➡️"
    
    def create_project_block(self, project: ProjectConfig, milestone_data: Dict[str, Any]) -> List[Dict]:
        """
        Create Slack blocks for a single project.
        
        Args:
            project: Project configuration
            milestone_data: Milestone data from GitHub
            
        Returns:
            List of Slack block elements
        """
        progress_percentage = milestone_data['progress_percentage']
        progress_bar = self.create_progress_bar(progress_percentage)
        status_emoji = self.get_status_emoji(progress_percentage)
        
        # Header block
        header_block = {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"{project.name}",
                "emoji": True
            }
        }
        
        # Progress section
        state_text = "Closed" if milestone_data.get('state') == 'closed' else "Open"
        
        progress_section = {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*Milestone:* <{milestone_data['html_url']}|{milestone_data['title']}>"
                },
                {
                    "type": "mrkdwn", 
                    "text": f"*Status:* {progress_percentage:.1f}% Complete"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Progress:* {milestone_data['closed_issues']}/{milestone_data['total_issues']} issues"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*State:* {state_text}"
                }
            ]
        }
        
        # Visual progress bar
        progress_bar_section = {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"```{progress_bar}``` {progress_percentage:.1f}%"
            }
        }
        
        # Additional info
        info_text = ""
        if milestone_data.get('description'):
            info_text += f"📝 *Description:* {milestone_data['description']}\n"
        
        if milestone_data.get('due_date'):
            due_date = datetime.fromisoformat(milestone_data['due_date'].replace('Z', '+00:00'))
            info_text += f"📅 *Due Date:* {due_date.strftime('%B %d, %Y')}\n"
        
        updated_at = datetime.fromisoformat(milestone_data['updated_at'].replace('Z', '+00:00'))
        info_text += f"*Last Updated:* {updated_at.strftime('%B %d, %Y at %I:%M %p')}"
        
        info_section = {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": info_text
            }
        }
        
        # Action buttons
        actions_block = {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "View Milestone",
                        "emoji": True
                    },
                    "url": milestone_data['html_url'],
                    "style": "primary"
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "View Issues",
                        "emoji": True
                    },
                    "url": f"https://github.com/{project.repo_owner}/{project.repo_name}/issues?q=milestone%3A{milestone_data['title']}"
                }
            ]
        }
        
        return [
            header_block,
            progress_section,
            progress_bar_section,
            info_section,
            actions_block,
            {"type": "divider"}  # Separator between projects
        ]
    
    def create_summary_blocks(self, milestones_data: List[tuple]) -> List[Dict]:
        """
        Create summary blocks for all milestones.
        
        Args:
            milestones_data: List of (milestone, milestone_data) tuples
            
        Returns:
            List of Slack block elements for summary
        """
        total_milestones = len(milestones_data)
        completed_milestones = sum(1 for _, data in milestones_data if data and data['progress_percentage'] >= 100)
        avg_progress = sum(data['progress_percentage'] for _, data in milestones_data if data) / total_milestones if total_milestones > 0 else 0
        
        summary_header = {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "Milestone Summary",
                "emoji": True
            }
        }
        
        summary_section = {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*Total Milestones:* {total_milestones}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Completed:* {completed_milestones}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Average Progress:* {avg_progress:.1f}%"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Report Date:* {datetime.now().strftime('%B %d, %Y')}"
                }
            ]
        }
        
        return [summary_header, summary_section, {"type": "divider"}]
    
    def send_slack_message(self, blocks: List[Dict]) -> bool:
        """
        Send formatted message to Slack using Blocks API.
        
        Args:
            blocks: List of Slack block elements
            
        Returns:
            True if successful, False otherwise
        """
        url = "https://slack.com/api/chat.postMessage"
        
        payload = {
            "channel": self.user_id,
            "blocks": blocks,
            "text": "Weekly Progress Report"  # Fallback text
        }
        
        try:
            response = requests.post(url, headers=self.slack_headers, json=payload)
            response.raise_for_status()
            
            result = response.json()
            if result.get('ok'):
                print("✅ Successfully sent progress report to Slack!")
                return True
            else:
                print(f"❌ Slack API error: {result.get('error', 'Unknown error')}")
                return False
                
        except requests.RequestException as e:
            print(f"❌ Error sending Slack message: {e}")
            return False
    
    def generate_weekly_report(self) -> None:
        """Generate and send weekly progress report."""
        print("🚀 Generating weekly progress report...")
        
        # Auto-discover all milestones
        print("🔍 Auto-discovering milestones...")
        self.milestones = self.discover_all_milestones()
        
        if not self.milestones:
            print("❌ No milestones found in the repository")
            return
        
        # Collect data for all milestones
        milestones_data = []
        for milestone in self.milestones:
            print(f"📊 Fetching data for {milestone.name}...")
            milestone_data = self.get_milestone_data(milestone)
            milestones_data.append((milestone, milestone_data))
        
        # Build Slack blocks
        all_blocks = []
        
        # Add project header
        project_header = {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"🚀 {self.repo_owner}/{self.repo_name} - Weekly Progress",
                "emoji": True
            }
        }
        all_blocks.append(project_header)
        
        # Add summary
        all_blocks.extend(self.create_summary_blocks(milestones_data))
        
        # Add individual milestone blocks
        for milestone, milestone_data in milestones_data:
            if milestone_data:
                all_blocks.extend(self.create_project_block(milestone, milestone_data))
            else:
                # Error block for failed milestones
                error_block = {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"❌ *{milestone.name}*\nFailed to fetch milestone data"
                    }
                }
                all_blocks.extend([error_block, {"type": "divider"}])
        
        # Remove last divider
        if all_blocks and all_blocks[-1].get("type") == "divider":
            all_blocks.pop()
        
        # Add footer
        footer_block = {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"📅 Generated on {datetime.now().strftime('%B %d, %Y at %I:%M %p')} | 🤖 Progress Bot"
                }
            ]
        }
        all_blocks.append(footer_block)
        
        # Send to Slack
        success = self.send_slack_message(all_blocks)
        
        if success:
            print(f"📈 Report sent! Tracked {len([d for _, d in milestones_data if d])} milestones successfully.")
        else:
            print("❌ Failed to send report.")
    
    def add_milestone(self, name: str, milestone_number: int, 
                     emoji: str = "📊", color: str = "#36a64f") -> None:
        """Add a new milestone to track."""
        milestone = ProjectConfig(name, self.repo_owner, self.repo_name, milestone_number, emoji, color)
        self.milestones.append(milestone)
        print(f"✅ Added milestone: {name}")
    
    def run_test(self) -> None:
        """Run a test report to verify everything works."""
        print("🧪 Running test report...")
        self.generate_weekly_report()


def main():
    """Main function to run the progress bot."""
    
    # Get tokens from environment variables
    BOT_TOKEN = os.getenv('SLACK_BOT_TOKEN')
    SLACK_USER_ID = os.getenv('SLACK_USER_ID')
    
    # Validate all required environment variables
    github_token = os.getenv('GITHUB_TOKEN')
    if not github_token:
        print("❌ Missing GITHUB_TOKEN environment variable")
        print("Please set: export GITHUB_TOKEN='your_github_token_here'")
        return
    
    if not BOT_TOKEN:
        print("❌ Missing SLACK_BOT_TOKEN environment variable")
        print("Please set: export SLACK_BOT_TOKEN='your_slack_bot_token_here'")
        return
    
    if not SLACK_USER_ID:
        print("❌ Missing SLACK_USER_ID environment variable")
        print("Please set: export SLACK_USER_ID='your_SLACK_USER_ID_here'")
        return
    
    # Initialize the bot
    bot = ProgressBot(
        slack_token=BOT_TOKEN,
        github_token=github_token,
        user_id=SLACK_USER_ID
    )
    
    # Check command line arguments or run test
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        bot.run_test()
    else:
        # Generate weekly report
        bot.generate_weekly_report()


if __name__ == '__main__':
    main()
