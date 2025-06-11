# CongressMCP

**Give your AI assistant access to comprehensive U.S. Congress data**

Connect any MCP-compatible AI client to live congressional data including bills, votes, committee reports, member information, and more. Research legislation, track voting patterns, and access official government documents through simple AI conversations.

✨ **6 organized toolsets • 92 operations** | 🏛️ **Official Congress.gov data** | 🚀 **Ready in 5 minutes**

## 🚀 Quick Start

**Get up and running in 5 minutes with our hosted service:**

### 1. Get Your API Key
Visit **[congressmcp.lawgiver.ai](https://congressmcp.lawgiver.ai)** to register and get your API key.

### 2. Install via NPM
```bash
npm install -g congressmcp
```

### 3. Configure Your MCP Client
Add this to your MCP client configuration (e.g., Claude Desktop):

```json
{
  "mcpServers": {
    "congressional-mcp": {
      "command": "npx",
      "args": ["-y", "congressmcp"],
      "env": {
        "CONGRESSMCP_API_KEY": "your-api-key-here"
      }
    }
  }
}
```

### 4. Start Reasoning
Restart your MCP client and start asking about bills, votes, committees, and more!

💡 **Example:** "Find recent climate change bills in the current Congress"

---

**Why use our hosted service?**
- ✅ Reliable uptime and automatic updates
- ✅ Professional support and documentation  
- ✅ No server management required

---

## 🗂️ What You Can Research

**6 comprehensive categories of congressional data:**

### 📋 **Bills & Legislation**
- Search and analyze bills, amendments, and treaties
- Track legislation through the legislative process  
- Access full bill text, voting records, and sponsor information
- Find bill summaries and legislative analysis

### 👥 **Members & Committees**
- Research representatives and senators by name, state, or district
- Find committee membership, leadership, and activities
- Track member voting patterns and sponsored legislation
- Access member biographical and contact information

### 🗳️ **Voting Records**
- Access detailed House and Senate voting records
- Research presidential nominations and confirmations
- Analyze voting patterns and member positions
- Find roll call votes and voting statistics

### 📰 **Congressional Records & Hearings**
- Search the Congressional Record and daily proceedings
- Access committee hearing transcripts and witness testimony
- Find House and Senate floor communications
- Browse historical congressional documents

### 📊 **Committee Reports & Intelligence**
- Access committee reports, prints, and publications
- Find committee meeting schedules, minutes, and agendas  
- Research committee-specific legislative activities
- Track committee markup sessions and votes

### 🔬 **Research & Analysis**
- Access Congressional Research Service (CRS) reports
- Get detailed Congress session information and statistics
- Use advanced search and filtering capabilities
- Access professional legislative research tools

## 💡 Example Use Cases

**📊 Policy Research**  
*"Find all climate change bills introduced in the 118th Congress and their current status"*

**🗳️ Voting Analysis**  
*"How did senators from California vote on recent healthcare legislation?"*

**👥 Member Research**  
*"Who are the current members of the House Energy and Commerce Committee?"*

**📋 Bill Tracking**  
*"What's the latest action on H.R. 1234 and who are its cosponsors?"*

**📰 Committee Activity**  
*"Show me recent hearings by the Senate Judiciary Committee on AI regulation"*

---

## 🛠️ Self-Hosting

**Need full control or want to contribute?** You can run your own instance.

**Note:** Self-hosting requires technical setup and maintenance. Our hosted service at [congressmcp.lawgiver.ai](https://congressmcp.lawgiver.ai) provides better reliability for most users.

### Quick Setup

1. **Clone and configure**:
   ```bash
   git clone https://github.com/your-org/congressmcp
   cd congressmcp
   cp .env.example .env
   ```

2. **Add your Congress.gov API key**:
   ```bash
   # Edit .env file
   CONGRESS_API_KEY=your_api_key_here
   ```

3. **Install and run**:
   ```bash
   pip install -r requirements.txt
   python run_server.py
   ```

### Advanced Configuration

For production deployments, see `.env.example` for complete configuration options including:
- Authentication and user management
- Database integration (Supabase)
- Payment processing (Stripe)  
- Email services (Resend)

## 📚 Resources

- **[Setup Guide](https://congressmcp.lawgiver.ai)** - Complete setup and usage documentation
- **[API Reference](./documentation/)** - Technical details for developers
- **[GitHub Issues](https://github.com/your-org/congressmcp/issues)** - Bug reports and feature requests

---

## 🤝 Contributing

We welcome contributions!

1. Fork the repository
2. Create a feature branch  
3. Add tests for new functionality
4. Submit a pull request

## 📄 License

Open source under the Sustainable Use License:
- ✅ Free to use and modify
- ✅ Self-hosting encouraged
- ✅ Commercial use allowed
- ❌ Cannot offer as competing hosted service

## 🆘 Support

- **Documentation** - [congressmcp.lawgiver.ai](https://congressmcp.lawgiver.ai)
- **GitHub Issues** - Bug reports and feature requests  
- **Email** - support@congressmcp.lawgiver.ai

---

**Built with ❤️ for government transparency and accessible civic data**
