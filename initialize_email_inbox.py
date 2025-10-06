"""
Initialize the dev email inbox with an empty index.html file
This creates the email inbox UI even when no emails have been sent yet.
"""
import os

# Create the dev_emails directory if it doesn't exist
dev_emails_dir = os.path.join('static', 'dev_emails')
os.makedirs(dev_emails_dir, exist_ok=True)

# Create an empty inbox page
index_path = os.path.join(dev_emails_dir, 'index.html')

html_content = """<!DOCTYPE html>
<html lang="fi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>📬 Development Email Inbox</title>
    <meta http-equiv="refresh" content="3">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        
        .header {
            background: white;
            padding: 30px;
            border-radius: 15px 15px 0 0;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        
        .header h1 {
            color: #333;
            font-size: 2rem;
            margin-bottom: 10px;
        }
        
        .header p {
            color: #666;
            font-size: 0.95rem;
        }
        
        .auto-refresh {
            display: inline-block;
            background: #10b981;
            color: white;
            padding: 5px 12px;
            border-radius: 20px;
            font-size: 0.85rem;
            margin-top: 10px;
            animation: pulse 2s infinite;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.7; }
        }
        
        .inbox {
            background: #f7fafc;
            border-radius: 0 0 15px 15px;
            padding: 30px;
            min-height: 400px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        
        .empty-state {
            text-align: center;
            padding: 80px 20px;
            color: #94a3b8;
        }
        
        .empty-state .icon {
            font-size: 5rem;
            margin-bottom: 20px;
            opacity: 0.5;
        }
        
        .empty-state h2 {
            font-size: 1.5rem;
            margin-bottom: 10px;
            color: #64748b;
        }
        
        .empty-state p {
            font-size: 1rem;
            line-height: 1.6;
        }
        
        .empty-state .steps {
            margin-top: 30px;
            text-align: left;
            display: inline-block;
            background: white;
            padding: 20px 30px;
            border-radius: 10px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.05);
        }
        
        .empty-state .steps li {
            margin: 10px 0;
            color: #475569;
        }
        
        .stats {
            background: #e0e7ff;
            padding: 15px 20px;
            border-radius: 10px;
            margin-bottom: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .stats .count {
            font-size: 1.5rem;
            font-weight: bold;
            color: #4f46e5;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📬 Development Email Inbox</h1>
            <p>All emails sent in development mode are saved here</p>
            <span class="auto-refresh">🔄 Auto-refreshes every 3 seconds</span>
        </div>
        
        <div class="inbox">
            <div class="stats">
                <div>
                    <strong>Total Emails:</strong> <span class="count">0</span>
                </div>
                <div style="color: #64748b;">
                    Waiting for first email...
                </div>
            </div>
            
            <div class="empty-state">
                <div class="icon">📭</div>
                <h2>No Emails Yet</h2>
                <p>Your inbox is empty. Start testing to see emails appear here!</p>
                
                <div class="steps">
                    <strong>Quick Start Guide:</strong>
                    <ol style="margin-left: 20px; margin-top: 10px;">
                        <li>Go to <a href="http://localhost:8000" target="_blank">http://localhost:8000</a></li>
                        <li>Create a new order as a customer</li>
                        <li>Come back here to see the confirmation email</li>
                        <li>Continue the workflow to generate more emails</li>
                    </ol>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
"""

with open(index_path, 'w', encoding='utf-8') as f:
    f.write(html_content)

print(f"✅ Email inbox initialized at: {index_path}")
print(f"🌐 Open in browser: http://localhost:8000/static/dev_emails/index.html")
print(f"📧 The inbox will update automatically when emails are sent!")
