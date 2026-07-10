import { Toaster as Sonner, type ToasterProps } from "sonner";

// Wrapper sottile attorno a sonner: il Toaster va montato una volta in App e poi
// si chiamano toast()/toast.error() da qualsiasi componente.
function Toaster(props: ToasterProps) {
  return <Sonner position="top-right" richColors closeButton {...props} />;
}

export { Toaster };
