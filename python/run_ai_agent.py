from ai_agent import CryptoAdvisor

def main():
    try:
        # Khởi tạo Crew
        print("🚀 Initializing CryptoAdvisor...")
        advisor = CryptoAdvisor()
        
        # Khởi chạy Crew
        print("📊 Creating crew...")
        crew = advisor.crew()
        
        print("✅ Crew created successfully!")
        print(f"Number of agents: {len(crew.agents)}")
        print(f"Number of tasks: {len(crew.tasks)}")
        
        # In thông tin các tasks
        print("\n📋 Tasks overview:")
        for i, task in enumerate(crew.tasks):
            print(f"Task {i+1}: {task.description[:50]}...")
        
        # Thay vì chạy từng task riêng lẻ, chạy toàn bộ crew với kickoff
        print("\n🔄 Running complete analysis...")
        
        # Chạy crew với input cho BTC
        result = crew.kickoff(inputs={"symbol": "BTC"})
        
        print("\n✅ Analysis completed!")
        print("Final Result:", result)
        
    except Exception as e:
        print(f"❌ Error occurred: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()