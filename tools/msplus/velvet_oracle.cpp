/* Test-only bridge to the unmodified, pinned MIT upstream core. */
#include <vector>
#include <cstddef>
#include <cstdint>
#include "velvet/processor.h"
extern "C" void velvet_reference(const float* input, float* output, unsigned frames,
                                 const double* controls, unsigned variant, int dynamic) {
    velvet::Processor processor;
    processor.prepare(44100,2);
    velvet::Parameters p;
    p.dynamic=dynamic!=0; p.amount=controls[0];p.lengthMs=controls[1];
    p.density=controls[2];p.refreshSeconds=controls[3];p.transitionMs=controls[4];
    p.decayDb=-controls[5];p.seed+=variant;
    processor.setParameters(p);
    std::vector<float> a(frames),b(frames),left(frames),right(frames);
    for(unsigned i=0;i<frames;++i){a[i]=input[2*i];b[i]=input[2*i+1];}
    const float* in[]={a.data(),b.data()}; float* out[]={left.data(),right.data()};
    processor.process(out,in,frames);
    for(unsigned i=0;i<frames;++i){output[2*i]=left[i];output[2*i+1]=right[i];}
}
