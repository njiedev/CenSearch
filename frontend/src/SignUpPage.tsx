import Corners from './Corners'
import { Battery, Clock, Timecode } from './Hud'
import type { ReactNode } from 'react'
import PhotoGrid from './PhotoGrid'

// The sign-up and log-in pages: the photo grid, blurred, behind a full-screen camera HUD.
// The HUD is fixed and decorative; the form scrolls underneath it.
export default function SignUpPage({ children }: { children: ReactNode }) {
  return (
    <>
      <PhotoGrid />
      <div className="rec-blur" aria-hidden="true" />
      <div className="rec-hud" aria-hidden="true">
        <Corners />
        <div className="vf-hud rec-top">
          <span className="vf-rec">
            <span className="vf-rec-dot" />
            Surveillance in progress
          </span>
          <Clock />
          <Battery />
        </div>
        <div className="vf-hud rec-bottom">
          <Timecode />
        </div>
      </div>
      <a className="rec-back" href="/">
        ← Back
      </a>
      <main className="rec-page" aria-labelledby="signup-title">
        {children}
      </main>
    </>
  )
}
