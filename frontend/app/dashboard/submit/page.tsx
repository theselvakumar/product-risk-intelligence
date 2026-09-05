'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { submitProduct } from '@/services/api';

interface ImageFilePreview {
  id: string;
  file: File;
  previewUrl: string;
  type: 'product' | 'packaging';
}

export default function SubmitProductPage() {
  const router = useRouter();

  // Option 1: Product URL
  const [productUrl, setProductUrl] = useState('');

  // Option 2: Image files
  const [images, setImages] = useState<ImageFilePreview[]>([]);

  // Option 3: Description
  const [productDescription, setProductDescription] = useState('');

  // Additional Fields
  const [notes, setNotes] = useState('');
  const [productName, setProductName] = useState('');
  const [brand, setBrand] = useState('');
  const [category, setCategory] = useState('HEALTH_SUPPLEMENTS_AND_NUTRACEUTICALS');
  const [manufacturer, setManufacturer] = useState('');
  const [fssaiLicense, setFssaiLicense] = useState('');

  // Submission UI state
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successData, setSuccessData] = useState<{
    case_number: string;
    case_id: string;
    product_id: string;
    status: string;
    title: string;
    sources_count: number;
    images_count: number;
  } | null>(null);

  // Client-side URL validation check
  const isUrlValid = (url: string) => {
    if (!url.trim()) return false;
    try {
      const parsed = new URL(url);
      return parsed.protocol === 'http:' || parsed.protocol === 'https:';
    } catch {
      return false;
    }
  };

  // Image Upload Handlers
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>, type: 'product' | 'packaging') => {
    if (!e.target.files) return;
    const filesArray = Array.from(e.target.files);

    const allowedMimeTypes = ['image/jpeg', 'image/png', 'image/webp', 'image/jpg'];
    const maxSizeBytes = 15 * 1024 * 1024; // 15 MB

    const newPreviews: ImageFilePreview[] = [];
    for (const f of filesArray) {
      if (!allowedMimeTypes.includes(f.type.toLowerCase())) {
        setError(`File '${f.name}' is not a supported format. Please upload JPEG, PNG, or WEBP images.`);
        return;
      }
      if (f.size > maxSizeBytes) {
        setError(`File '${f.name}' exceeds the maximum permissible limit of 15MB.`);
        return;
      }
      newPreviews.push({
        id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
        file: f,
        previewUrl: URL.createObjectURL(f),
        type,
      });
    }

    setImages((prev) => [...prev, ...newPreviews]);
    setError(null);
    e.target.value = '';
  };

  const handleRemoveImage = (id: string) => {
    setImages((prev) => {
      const removed = prev.find((img) => img.id === id);
      if (removed) {
        URL.revokeObjectURL(removed.previewUrl);
      }
      return prev.filter((img) => img.id !== id);
    });
  };

  // Submission validation
  const hasUrl = Boolean(productUrl.trim());
  const hasImages = images.length > 0;
  const hasDesc = Boolean(productDescription.trim());
  const isInputValid = hasUrl || hasImages || hasDesc;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isInputValid) {
      setError('Please provide at least one input option: Product URL, Uploaded Images, or Product Description.');
      return;
    }

    if (hasUrl && !isUrlValid(productUrl)) {
      setError('Please enter a valid product URL starting with http:// or https://');
      return;
    }

    setLoading(true);
    setError(null);
    setSuccessData(null);

    try {
      const formData = new FormData();
      if (hasUrl) formData.append('product_url', productUrl.trim());
      if (hasDesc) formData.append('product_description', productDescription.trim());
      if (notes.trim()) formData.append('notes', notes.trim());
      if (productName.trim()) formData.append('product_name', productName.trim());
      if (brand.trim()) formData.append('brand', brand.trim());
      if (category.trim()) formData.append('category', category.trim());
      if (manufacturer.trim()) formData.append('manufacturer', manufacturer.trim());
      if (fssaiLicense.trim()) formData.append('fssai_license_number', fssaiLicense.trim());

      // Append image files
      images.forEach((img) => {
        if (img.type === 'product') {
          formData.append('product_images', img.file);
        } else {
          formData.append('packaging_images', img.file);
        }
      });

      const res = await submitProduct(formData);
      setSuccessData(res);
      // Redirect to the analysis page for manual analysis by the authority officer
      router.push(`/dashboard/cases/${res.case_id}/analysis`);
    } catch (err: any) {
      setError(err.message || 'Failed to submit product for surveillance.');
    } finally {
      setLoading(false);
    }
  };

  // Demo autofill templates
  const handleAutofillUrl = () => {
    setProductUrl('https://example-mart.in/products/vedika-diabetic-care-extract');
    setProductDescription('');
    setProductName('Vedika Diabetic Care Herbal Extract 500ml');
    setBrand('Vedika Botanicals');
    setCategory('HEALTH_SUPPLEMENTS_AND_NUTRACEUTICALS');
    setNotes('Unverified curative claims under Section 24 on e-commerce listing.');
  };

  const handleAutofillDesc = () => {
    setProductUrl('');
    setProductDescription(
      'Proprietary Herbal Weight Loss Elixir. Declared Ingredients: Garcinia extract 80%, Chromium Picolinate 400mcg, preservative 211. Package Claims: "Guaranteed 10kg fat loss in 14 days without diet alteration."'
    );
    setProductName('SlimVital Herbal Elixir 200ml');
    setBrand('SlimVital Nutraceuticals');
    setCategory('HEALTH_SUPPLEMENTS_AND_NUTRACEUTICALS');
    setNotes('High suspicion of prohibited claims and undeclared stimulant additives.');
  };

  const handleAutofillMixed = () => {
    setProductUrl('https://supermart.in/ayur-shilajit-resin');
    setProductDescription(
      'Himalayan Gold Shilajit Pure Resin 20g. Contains fulvic acid 85%. Advertised for stamina, athletic performance, and anti-aging.'
    );
    setProductName('Himalayan Gold Shilajit Pure Resin 20g');
    setBrand('MountainHerbs India');
    setCategory('AYURVEDIC_PROPRIETARY');
    setNotes('Check compliance against FSSAI Nutraceutical Regulations 2022 and permissible heavy metal limits.');
  };

  return (
    <div className="max-w-5xl mx-auto space-y-6 pb-12">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-emerald-100 dark:bg-emerald-950/80 text-emerald-700 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-800">
              Phase 5 Active
            </span>
            <span className="text-xs text-slate-500 dark:text-slate-400">
              Regulatory Surveillance &amp; Case Creation
            </span>
          </div>
          <h2 className="text-2xl font-black tracking-tight text-slate-900 dark:text-white">
            Product Submission &amp; Surveillance Intake
          </h2>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Authority submission workflow under Food Safety &amp; Standards Act, 2006. Submit via URL, Packaging Images, Description, or mixed evidence.
          </p>
        </div>

        {/* Preset demo shortcuts */}
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-[11px] font-semibold text-slate-400">Autofill:</span>
          <button
            type="button"
            onClick={handleAutofillUrl}
            className="text-xs font-semibold px-2.5 py-1.5 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
          >
            URL Sample
          </button>
          <button
            type="button"
            onClick={handleAutofillDesc}
            className="text-xs font-semibold px-2.5 py-1.5 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
          >
            Description Sample
          </button>
          <button
            type="button"
            onClick={handleAutofillMixed}
            className="text-xs font-semibold px-2.5 py-1.5 rounded-lg border border-emerald-300 dark:border-emerald-800 bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300 hover:bg-emerald-100 dark:hover:bg-emerald-900/50 transition-colors"
          >
            Mixed Evidence &rarr;
          </button>
        </div>
      </div>

      {/* Success Notification Card */}
      {successData && (
        <div className="p-6 rounded-2xl bg-emerald-50 dark:bg-emerald-950/80 border border-emerald-200 dark:border-emerald-800 shadow-sm animate-in fade-in zoom-in-95 duration-200">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-emerald-500 text-white flex items-center justify-center font-bold text-lg shadow-sm">
                &#10003;
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="text-base font-bold text-emerald-900 dark:text-emerald-200">
                    Regulatory Case Registered Successfully
                  </h3>
                  <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-emerald-200 dark:bg-emerald-900 text-emerald-900 dark:text-emerald-200">
                    {successData.status}
                  </span>
                </div>
                <p className="text-xs font-mono text-emerald-800 dark:text-emerald-300 mt-0.5">
                  Docket Number: <span className="font-bold">{successData.case_number}</span>
                </p>
              </div>
            </div>
            <Link
              href="/dashboard/cases"
              className="text-xs font-bold px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white transition-colors"
            >
              View All Cases &rarr;
            </Link>
          </div>

          <div className="mt-4 pt-4 border-t border-emerald-200 dark:border-emerald-800/80 grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
            <div>
              <span className="text-emerald-700 dark:text-emerald-400 block font-medium">Status</span>
              <span className="font-bold text-emerald-900 dark:text-white font-mono">SUBMITTED</span>
            </div>
            <div>
              <span className="text-emerald-700 dark:text-emerald-400 block font-medium">Sources Recorded</span>
              <span className="font-bold text-emerald-900 dark:text-white">{successData.sources_count} source(s)</span>
            </div>
            <div>
              <span className="text-emerald-700 dark:text-emerald-400 block font-medium">Images Stored</span>
              <span className="font-bold text-emerald-900 dark:text-white">{successData.images_count} image file(s)</span>
            </div>
            <div>
              <span className="text-emerald-700 dark:text-emerald-400 block font-medium">Queue</span>
              <span className="font-bold text-emerald-900 dark:text-white">Ready for Analysis</span>
            </div>
          </div>
        </div>
      )}

      {/* Error Message */}
      {error && (
        <div className="p-4 rounded-xl bg-red-50 dark:bg-red-950/80 border border-red-200 dark:border-red-800 text-xs text-red-800 dark:text-red-300 font-semibold flex items-center justify-between">
          <span>{error}</span>
          <button onClick={() => setError(null)} className="text-red-500 hover:text-red-700 font-bold ml-2">
            &times;
          </button>
        </div>
      )}

      {/* Main Submission Form */}
      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Section 1: Three Primary Submission Options */}
        <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-6 sm:p-8 shadow-sm space-y-8">
          <div className="border-b border-slate-100 dark:border-slate-800 pb-4">
            <h3 className="text-sm font-black uppercase tracking-wider text-slate-800 dark:text-slate-200">
              1. Primary Product Evidence Modalities
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
              Authority officers may supply any combination of Option 1 (URL), Option 2 (Images), or Option 3 (Description).
            </p>
          </div>

          {/* Option 1: Product URL */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300 flex items-center gap-2">
                <span className="w-5 h-5 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 text-[10px] flex items-center justify-center font-black">
                  1
                </span>
                Option 1: Product Web / E-Commerce URL
              </label>
              {productUrl && (
                <span
                  className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                    isUrlValid(productUrl)
                      ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300'
                      : 'bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300'
                  }`}
                >
                  {isUrlValid(productUrl) ? 'Valid Web Link Format' : 'Requires http:// or https://'}
                </span>
              )}
            </div>
            <input
              type="url"
              value={productUrl}
              onChange={(e) => setProductUrl(e.target.value)}
              placeholder="https://www.amazon.in/dp/... or quick-commerce platform product link"
              className="w-full rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-950 px-4 py-2.5 text-sm font-mono text-slate-900 dark:text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 transition-all"
            />
          </div>

          {/* Option 2: Image Uploads */}
          <div className="space-y-4 pt-4 border-t border-slate-100 dark:border-slate-800/80">
            <label className="text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300 flex items-center gap-2">
              <span className="w-5 h-5 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 text-[10px] flex items-center justify-center font-black">
                2
              </span>
              Option 2: Packaging &amp; Product Image Evidence (JPEG, PNG, WEBP &bull; Max 15MB)
            </label>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Product Front / Commercial Images Dropzone */}
              <div className="p-4 rounded-xl border-2 border-dashed border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/40 hover:border-emerald-500/50 transition-colors">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-bold text-slate-800 dark:text-slate-200">
                    Product Front / Primary Pack
                  </span>
                  <span className="text-[10px] text-slate-400">Front of Pack</span>
                </div>
                <input
                  type="file"
                  multiple
                  accept="image/jpeg,image/png,image/webp"
                  onChange={(e) => handleFileChange(e, 'product')}
                  className="w-full text-xs text-slate-500 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-emerald-50 dark:file:bg-emerald-950/60 file:text-emerald-700 dark:file:text-emerald-300 hover:file:bg-emerald-100 cursor-pointer"
                />
              </div>

              {/* Packaging / Nutrition Panel Dropzone */}
              <div className="p-4 rounded-xl border-2 border-dashed border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/40 hover:border-emerald-500/50 transition-colors">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-bold text-slate-800 dark:text-slate-200">
                    Packaging / Nutrition &amp; Ingredients Panel
                  </span>
                  <span className="text-[10px] text-slate-400">Back / Side Panels</span>
                </div>
                <input
                  type="file"
                  multiple
                  accept="image/jpeg,image/png,image/webp"
                  onChange={(e) => handleFileChange(e, 'packaging')}
                  className="w-full text-xs text-slate-500 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-emerald-50 dark:file:bg-emerald-950/60 file:text-emerald-700 dark:file:text-emerald-300 hover:file:bg-emerald-100 cursor-pointer"
                />
              </div>
            </div>

            {/* Real-time Image Previews */}
            {images.length > 0 && (
              <div className="pt-2">
                <p className="text-[11px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-2">
                  Uploaded Image Previews ({images.length} file{images.length > 1 ? 's' : ''})
                </p>
                <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-6 gap-3">
                  {images.map((img) => (
                    <div
                      key={img.id}
                      className="relative group rounded-xl overflow-hidden border border-slate-200 dark:border-slate-700 bg-slate-100 dark:bg-slate-800"
                    >
                      <img
                        src={img.previewUrl}
                        alt={img.file.name}
                        className="w-full h-24 object-cover"
                      />
                      <div className="p-1.5 bg-white dark:bg-slate-900 border-t border-slate-200 dark:border-slate-700 text-[10px]">
                        <p className="font-semibold truncate text-slate-800 dark:text-slate-200">{img.file.name}</p>
                        <p className="text-slate-400">{(img.file.size / 1024).toFixed(0)} KB</p>
                      </div>
                      <button
                        type="button"
                        onClick={() => handleRemoveImage(img.id)}
                        className="absolute top-1 right-1 w-5 h-5 rounded-full bg-red-600 text-white flex items-center justify-center text-xs font-bold opacity-80 hover:opacity-100 transition-opacity"
                        title="Remove image"
                      >
                        &times;
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Option 3: Product Description */}
          <div className="space-y-2 pt-4 border-t border-slate-100 dark:border-slate-800/80">
            <div className="flex items-center justify-between">
              <label className="text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300 flex items-center gap-2">
                <span className="w-5 h-5 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 text-[10px] flex items-center justify-center font-black">
                  3
                </span>
                Option 3: Product Description / Physical Inspection Notes
              </label>
              <span className="text-[10px] text-slate-400 font-mono">
                {productDescription.length} characters
              </span>
            </div>
            <textarea
              rows={3}
              value={productDescription}
              onChange={(e) => setProductDescription(e.target.value)}
              placeholder="Paste declared product claims, ingredient statements, physical sampling observations, or officer transcription..."
              className="w-full rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-950 p-3.5 text-sm text-slate-900 dark:text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 transition-all"
            />
          </div>
        </div>

        {/* Section 2: Product Metadata & Regulatory Classification (Optional) */}
        <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-6 sm:p-8 shadow-sm space-y-6">
          <div className="border-b border-slate-100 dark:border-slate-800 pb-4">
            <h3 className="text-sm font-black uppercase tracking-wider text-slate-800 dark:text-slate-200">
              2. Product Identification &amp; Statutory Notes (Optional)
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
              Provide commercial identification metadata if available. If left blank, the system will derive identifiers automatically.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
            {/* Product Name */}
            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300 mb-1.5">
                Product Commercial Name
              </label>
              <input
                type="text"
                value={productName}
                onChange={(e) => setProductName(e.target.value)}
                placeholder="e.g. PureNature Herbal Diabetic Extract 500ml"
                className="w-full rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-950 px-3.5 py-2.5 text-sm text-slate-900 dark:text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500"
              />
            </div>

            {/* Brand */}
            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300 mb-1.5">
                Brand / Trademark
              </label>
              <input
                type="text"
                value={brand}
                onChange={(e) => setBrand(e.target.value)}
                placeholder="e.g. PureNature Brands"
                className="w-full rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-950 px-3.5 py-2.5 text-sm text-slate-900 dark:text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500"
              />
            </div>

            {/* Regulatory Category */}
            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300 mb-1.5">
                Statutory Product Category
              </label>
              <select
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                className="w-full rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-950 px-3.5 py-2.5 text-sm text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500"
              >
                <option value="HEALTH_SUPPLEMENTS_AND_NUTRACEUTICALS">Health Supplements &amp; Nutraceuticals</option>
                <option value="AYURVEDIC_PROPRIETARY">Ayurvedic / Proprietary Medicine</option>
                <option value="INFANT_FOODS_AND_FORMULA">Infant Foods &amp; Nutrition Formula</option>
                <option value="EDIBLE_OILS_AND_FATS">Edible Oils &amp; Fats</option>
                <option value="CEREAL_AND_CONFECTIONERY">Cereal &amp; Confectionery</option>
                <option value="BEVERAGES_TEA_AND_COFFEE">Beverages (Tea, Coffee, Energy Drinks)</option>
                <option value="DAIRY_AND_ANALOGUES">Dairy Products &amp; Analogues</option>
                <option value="HONEY_AND_PRESERVES">Honey, Syrups &amp; Preserves</option>
              </select>
            </div>

            {/* FSSAI License */}
            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300 mb-1.5">
                14-Digit FSSAI License # (if declared)
              </label>
              <input
                type="text"
                maxLength={14}
                value={fssaiLicense}
                onChange={(e) => setFssaiLicense(e.target.value)}
                placeholder="10018022007890"
                className="w-full rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-950 px-3.5 py-2.5 text-sm font-mono text-slate-900 dark:text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500"
              />
            </div>

            {/* Manufacturer */}
            <div className="sm:col-span-2">
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300 mb-1.5">
                Manufacturer / Importer &amp; Premise Location
              </label>
              <input
                type="text"
                value={manufacturer}
                onChange={(e) => setManufacturer(e.target.value)}
                placeholder="e.g. PureNature Agro Labs Pvt Ltd, Industrial Area, Haridwar"
                className="w-full rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-950 px-3.5 py-2.5 text-sm text-slate-900 dark:text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500"
              />
            </div>

            {/* Optional Officer Notes */}
            <div className="sm:col-span-2">
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300 mb-1.5">
                Officer Surveillance Notes &amp; Observations
              </label>
              <textarea
                rows={2}
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Detail suspected non-compliances under Section 23/24 (e.g. missing allergen disclaimer, unapproved claims, or packaging anomalies)."
                className="w-full rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-950 p-3 text-sm text-slate-900 dark:text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500"
              />
            </div>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center justify-between p-4 bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm">
          <div className="text-xs text-slate-500 dark:text-slate-400">
            {isInputValid ? (
              <span className="text-emerald-600 dark:text-emerald-400 font-semibold flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-emerald-500 inline-block"></span>
                Ready for submission (Initial status: SUBMITTED)
              </span>
            ) : (
              <span className="text-amber-600 dark:text-amber-400">
                &bull; Please enter a URL, upload an image, or type a description to proceed.
              </span>
            )}
          </div>

          <div className="flex items-center gap-3">
            <Link
              href="/dashboard"
              className="px-4 py-2.5 rounded-xl text-xs font-semibold text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            >
              Cancel
            </Link>
            <button
              type="submit"
              disabled={loading || !isInputValid}
              className="px-6 py-2.5 rounded-xl text-xs font-bold text-white bg-emerald-600 hover:bg-emerald-700 shadow-sm transition-colors disabled:opacity-50 flex items-center gap-2"
            >
              {loading && (
                <svg className="animate-spin h-3.5 w-3.5 text-white" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
                </svg>
              )}
              {loading ? 'Creating Investigation Case...' : 'Submit & Create Case Docket'}
            </button>
          </div>
        </div>
      </form>
    </div>
  );
}
