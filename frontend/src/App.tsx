import Headlines from './Headlines'
import Logo from './Logo'
import NavBar from './NavBar'
import PhotoGrid from './PhotoGrid'
import Viewfinder from './Viewfinder'

export default function App() {
  return (
    <>
      <PhotoGrid />
      <Headlines />
      <NavBar />
      <main>
        <section className="hero" id="top">
          <Logo />
          <p className="scroll-hint">Scroll</p>
        </section>
        <section className="desk" id="about">
          <Viewfinder />
        </section>
      </main>
    </>
  )
}
