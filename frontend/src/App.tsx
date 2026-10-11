import Logo from './Logo'
import PhotoGrid from './PhotoGrid'
import SignUp from './SignUp'
import Viewfinder from './Viewfinder'

export default function App() {
  return (
    <>
      <PhotoGrid />
      <main>
        <section className="hero" id="top">
          <Logo />
          <p className="scroll-hint">Scroll</p>
        </section>
        {/* One blur layer behind both sections, so there's no seam between them. */}
        <div className="blurred">
          <section className="desk" id="about">
            <Viewfinder />
          </section>
          <section className="signup" id="signup" aria-labelledby="signup-title">
            <SignUp />
          </section>
        </div>
      </main>
    </>
  )
}
