from chunks import summarize_pdf, build_chunks
import asyncio
def main():

    q = input('>>')
    chunk_list = build_chunks(
        'infi.pptx'
    )
    print(chunk_list)
    print('--------------------------------------------')
    print(asyncio.run(summarize_pdf(chunk_list, 'infi.pptx')))

if __name__ == "__main__":
    main()