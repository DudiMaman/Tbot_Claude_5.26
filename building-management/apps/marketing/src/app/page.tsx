import { Hero } from '@/components/hero';
import { Features } from '@/components/features';
import { WhoItsFor } from '@/components/who-its-for';
import { Pricing } from '@/components/pricing';
import { Testimonials } from '@/components/testimonials';
import { Faq } from '@/components/faq';
import { Footer } from '@/components/footer';
import { Header } from '@/components/header';

export default function Home() {
  return (
    <main className="min-h-screen bg-gradient-to-b from-white to-slate-50">
      <Header />
      <Hero />
      <Features />
      <WhoItsFor />
      <Pricing />
      <Testimonials />
      <Faq />
      <Footer />
    </main>
  );
}
