import sys
import json
from ai_agent import CryptoNewsResearcher


from datetime import datetime


def run_news_analysis(current_date):
   """
   Run crypto news analysis


   Args:
       current_date (str): Current date in YYYY-MM-DD format


   Returns:
       dict: Structured analysis results
   """
   try:
       print(f"Initializing CryptoNewsResearcher for date: {current_date}")
       crew_instance = CryptoNewsResearcher()
      
       print("Starting crew kickoff...")
       result = crew_instance.crew().kickoff(inputs={
           'current_date': current_date
       })
      
       print("Crew execution completed successfully")
       return {
           'success': True,
           'data': str(result),  # Convert to string to avoid serialization issues
           'analysis_date': current_date,
           'timestamp': datetime.now().isoformat(),
           'output_file': 'crypto_market_news.md'
       }
   except Exception as e:
       print(f"Error details: {traceback.format_exc()}")
       return {
           'success': False,
           'error': str(e),
           'error_details': traceback.format_exc(),
           'analysis_date': current_date,
           'timestamp': datetime.now().isoformat()
       }


def main():
   """Main function to run the script"""

   current_date = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime('%Y-%m-%d')
  
   print(f"Starting crypto news analysis for {current_date}")
   result = run_news_analysis(current_date)
  
   print(json.dumps(result, indent=2, ensure_ascii=False))
  
   if result['success']:
       print(f"\n✅ News analysis complete!")
       print(f"📅 Analysis date: {result['analysis_date']}")
       print(f"📄 Results saved to: {result['output_file']}")
   else:
       print(f"\n❌ An error occurred: {result['error']}")
       if 'error_details' in result:
           print(f"Error details: {result['error_details']}")


if __name__ == "__main__":
   main()

