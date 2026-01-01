"""Test script to verify Word document resume extraction."""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from matching.resume_loader import ResumeLoader
from config.config import get_config


def main():
    print("=" * 60)
    print("Testing Resume Extraction from Word Document")
    print("=" * 60)
    
    config = get_config()
    loader = ResumeLoader(config)
    
    # Check if resume file exists
    resume_path = Path(config.resume_path)
    print(f"\nLooking for resume at: {resume_path}")
    print(f"Resume file exists: {resume_path.exists()}")
    
    if not resume_path.exists():
        print("\n⚠️  ERROR: Resume file not found!")
        print(f"Expected location: {resume_path.absolute()}")
        print("\nPlease ensure you have placed your resume file at:")
        print(f"  - data/resume.docx (or)")
        print(f"  - data/master_resume.docx")
        print("\nOr set RESUME_PATH in your .env file")
        return
    
    # Try to load the resume
    print("\n" + "-" * 60)
    print("Extracting text from resume...")
    print("-" * 60)
    
    try:
        resume_text = loader.load_text()
        
        if not resume_text:
            print("\n⚠️  WARNING: Resume text is empty!")
            return
        
        # Display extraction results
        print(f"\n✓ Successfully extracted resume text!")
        print(f"\nResume Statistics:")
        print(f"  - Total characters: {len(resume_text)}")
        print(f"  - Total words: {len(resume_text.split())}")
        print(f"  - Total lines: {len(resume_text.splitlines())}")
        
        # Show preview
        print(f"\n" + "=" * 60)
        print("Resume Text Preview (first 500 characters):")
        print("=" * 60)
        preview = resume_text[:500]
        print(preview)
        if len(resume_text) > 500:
            print("\n... (text truncated for preview)")
        
        # Test caching
        print(f"\n" + "-" * 60)
        print("Testing cache functionality...")
        print("-" * 60)
        cached_text = loader.load_text()
        if cached_text == resume_text:
            print("✓ Cache working correctly - same text returned")
        else:
            print("⚠️  WARNING: Cache may not be working properly")
        
        print(f"\n" + "=" * 60)
        print("✓ Resume extraction test PASSED!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ ERROR: Failed to extract resume text!")
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {str(e)}")
        import traceback
        print("\nFull traceback:")
        traceback.print_exc()


if __name__ == "__main__":
    main()
