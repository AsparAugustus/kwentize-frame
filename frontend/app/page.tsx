import { getFrameMetadata } from '@coinbase/onchainkit/frame';
import type { Metadata } from 'next';
import { NEXT_PUBLIC_URL } from './config';
import { Analytics } from "@vercel/analytics/react"

const frameMetadata = getFrameMetadata({
  buttons: [
    {
      label: 'Start Kwentize!',
    }
  ],
  image: {
    src: `${NEXT_PUBLIC_URL}/kwentize.png`,
    aspectRatio: '1:1',
  },
  postUrl: `${NEXT_PUBLIC_URL}/api/frame`,
});

export const metadata: Metadata = {
  title: 'https://github.com/AsparAugustus',
  description: 'LFG',
  openGraph: {
    title: 'https://github.com/AsparAugustus',
    description: 'LFG',
    images: [`${NEXT_PUBLIC_URL}/kwentize.png`],
  },
  other: {
    ...frameMetadata,
  },
};

export default function Page() {
  return (
    <>
    <Analytics />
      <h1>https://github.com/AsparAugustus</h1>
    </>
  );
}
